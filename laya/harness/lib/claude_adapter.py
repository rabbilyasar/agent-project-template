"""Claude ModelAdapter implementation (Anthropic Messages API).

Never makes a real HTTP call itself, and never imports an HTTP/network library at all --
the adapter is constructed with an injectable `transport(request_body: dict) -> dict`
callable, exactly like deepseek_adapter.DeepSeekAdapter. Model-free tests inject a fake
transport, so this module has zero network dependency and importing it never requires
`anthropic`/`requests`/`httpx`/an API key/network access.

Reuses the existing prompt contracts (laya/harness/prompts/*.json) as the sole source of
decision_question/allowed_output_values -- no second prompt contract, no rewritten
decision semantics, identical in spirit to laya_adapter.py and deepseek_adapter.py.

Output validation reuses deepseek_adapter.parse_decision_content and
JSON_TRANSPORT_INSTRUCTION_TEMPLATE by import (deepseek_adapter.py itself is not
modified): both are pure, provider-neutral text/JSON logic with no DeepSeek-specific
content, so importing them here is reuse, not a refactor -- the same "smallest possible
change" a provider-neutral extraction would have made, without touching the existing,
already-approved DeepSeek adapter file.

Claude-specific: _unwrap_whole_response_markdown_fence() runs before the shared parser,
because Claude Haiku 4.5 was observed wrapping its entire JSON answer in a markdown code
fence despite the shared transport instruction explicitly forbidding it (see the historical
phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z run, and ADR on Phase 4
adapter reuse in docs/decisions.md). It only unwraps a single fence enclosing the ENTIRE
response -- it never searches for or extracts a JSON object embedded in surrounding prose,
so the shared parser's no-broad-extraction guarantee is preserved for any other malformed
shape.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from adapter_base import PredictionEnvelope
from deepseek_adapter import JSON_TRANSPORT_INSTRUCTION_TEMPLATE, parse_decision_content

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

# Claude Haiku 4.5 (unlike DeepSeek Flash, observed in the historical
# phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z run) wraps its JSON answer in
# a markdown code fence despite JSON_TRANSPORT_INSTRUCTION_TEMPLATE explicitly telling it not
# to. This pattern only matches when a single fence encloses the ENTIRE response with nothing
# else outside it -- never a fence found inside a larger blob of prose, which stays rejected by
# the shared parser exactly as before. It is a fence-unwrap, not JSON extraction.
_WHOLE_RESPONSE_FENCE_RE = re.compile(r"^```(?:[a-zA-Z0-9_+-]*)?\s*\n(.*?)\n?```$", re.DOTALL)


def _unwrap_whole_response_markdown_fence(text: str) -> str:
    """Strips a single markdown code fence when it wraps the entire response text, otherwise
    returns text unchanged. Deliberately narrow: does not search for or extract a JSON object
    embedded anywhere within surrounding prose."""
    match = _WHOLE_RESPONSE_FENCE_RE.match(text.strip())
    return match.group(1).strip() if match else text

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Cheapest/fastest current tier, consistent with the same cost-minimization choice
# already made for DeepSeek (flash, not pro) and Laya (a small local model) -- a System-1
# decision engine baseline should test the cheap tier first, not the flagship model.
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_TOKENS = 64


class ClaudeAdapterError(Exception):
    """Raised only for a programming/contract error (unknown decision_type, missing
    prompt contract file) -- never for a model-side/transport/API failure, which becomes
    a PredictionEnvelope with valid_prediction=False instead."""


def build_model_identifier(model: str) -> str:
    """Deterministic, stable construction -- includes the actual model used, never
    silently relies on an API default."""
    return f"claude:{model}:direct-api"


def _load_contract(decision_type: str) -> dict:
    path = PROMPTS_DIR / f"{decision_type}.json"
    if not path.exists():
        raise ClaudeAdapterError(f"no prompt contract for decision_type={decision_type!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_user_content(rendered_prompt: Any) -> str:
    if isinstance(rendered_prompt, str):
        return rendered_prompt
    return json.dumps(rendered_prompt, sort_keys=True)


def build_request_body(
    decision_type: str, rendered_prompt: Any, allowed_output_values: list[str],
    model: str, max_tokens: int,
) -> dict:
    """Builds the Anthropic Messages API request body. decision_question is the
    contract's own text, verbatim -- it carries all the real semantics, unmodified. The
    JSON transport instruction (shared with the DeepSeek adapter, imported not
    duplicated) describes only how the answer must be shaped on the wire."""
    contract = _load_contract(decision_type)
    transport_instruction = JSON_TRANSPORT_INSTRUCTION_TEMPLATE.format(
        values=", ".join(repr(v) for v in allowed_output_values)
    )
    system_content = f"{contract['decision_question']}\n\n{transport_instruction}"
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_content,
        "messages": [{"role": "user", "content": _render_user_content(rendered_prompt)}],
    }


class ClaudeAdapter:
    """ModelAdapter implementation over an injectable HTTP transport callable:
    `transport(request_body: dict) -> dict`, returning the full parsed JSON response body
    (the Anthropic Messages API's response shape). `transport` may raise for any
    transport/API failure (timeout, non-2xx, auth failure) -- the adapter converts any
    such exception into a PredictionEnvelope, never a crash, and never retries."""

    def __init__(self, transport: Callable[[dict], dict], model: str = DEFAULT_MODEL, max_tokens: int = DEFAULT_MAX_TOKENS):
        self.transport = transport
        self.model = model
        self.max_tokens = max_tokens
        self.model_identifier = build_model_identifier(model)

    def predict(self, decision_type: str, rendered_prompt: Any, allowed_output_values: list[str]) -> PredictionEnvelope:
        request_body = build_request_body(decision_type, rendered_prompt, allowed_output_values, self.model, self.max_tokens)

        t0 = time.perf_counter()
        try:
            response = self.transport(request_body)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return PredictionEnvelope(
                predicted_value=None, valid_prediction=False,
                error=f"api_error: {type(e).__name__}: {e}",
                latency_ms=elapsed_ms, input_tokens=None, output_tokens=None,
                cache_read_tokens=None, cache_write_tokens=None,
                model_identifier=self.model_identifier, raw_response=None,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000

        return self._envelope_from_response(response, allowed_output_values, elapsed_ms)

    def _envelope_from_response(self, response: dict, allowed_output_values: list[str], elapsed_ms: float) -> PredictionEnvelope:
        raw_response = dict(response) if isinstance(response, dict) else {"value": response}

        try:
            blocks = response["content"]
            text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        except (KeyError, TypeError):
            return PredictionEnvelope(
                predicted_value=None, valid_prediction=False,
                error="malformed_output: missing_content",
                latency_ms=elapsed_ms, input_tokens=None, output_tokens=None,
                cache_read_tokens=None, cache_write_tokens=None,
                model_identifier=self.model_identifier, raw_response=raw_response,
            )

        usage = response.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        cache_read_tokens = usage.get("cache_read_input_tokens")
        cache_write_tokens = usage.get("cache_creation_input_tokens")

        decision, error = parse_decision_content(_unwrap_whole_response_markdown_fence(text), allowed_output_values)
        valid = error is None

        return PredictionEnvelope(
            predicted_value=decision,
            valid_prediction=valid,
            error=error,
            latency_ms=elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            model_identifier=self.model_identifier,
            # Never manufactured: no directly supported, semantically valid class-
            # probability source for an arbitrary JSON decision from this API.
            confidence=None,
            probability_distribution=None,
            raw_response=raw_response,
        )
