"""DeepSeek ModelAdapter implementation (OpenAI-compatible chat-completions wire format).

Never makes a real HTTP call itself, and never imports an HTTP/network library at all --
the adapter is constructed with an injectable `transport(request_body: dict) -> dict`
callable (any function: real HTTP client, fake, or stub). Model-free tests inject a fake
transport, so this module has zero network dependency and importing it never requires
`requests`/`httpx`/an API key/network access.

Reuses the existing prompt contracts (laya/harness/prompts/*.json) as the sole source of
decision_question/allowed_output_values, exactly like laya_adapter.py -- no second prompt
contract, no rewritten decision semantics. The only DeepSeek-specific addition is the JSON
transport instruction appended to the system message, which expresses how the answer must
be shaped on the wire, not what is being asked.

Never trusts `response_format: {"type": "json_object"}` alone: the returned content is
independently parsed and validated (exactly one "decision" string key, no extra keys, no
prose wrapping the JSON, value in allowed_output_values) before being treated as a
prediction. Malformed output measures the model's actual contract adherence -- it is never
silently repaired.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from adapter_base import PredictionEnvelope

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

DEFAULT_MODEL = "deepseek-flash"
DEFAULT_THINKING = {"type": "disabled"}
DEFAULT_REASONING_EFFORT = "none"

JSON_TRANSPORT_INSTRUCTION_TEMPLATE = (
    'Respond with exactly one JSON object of the form {{"decision": "<value>"}}, where '
    '<value> is exactly one of: {values}. Output nothing else -- no surrounding text, no '
    'markdown code fence, no explanation, no additional keys.'
)


class DeepSeekAdapterError(Exception):
    """Raised only for a programming/contract error (unknown decision_type, missing
    prompt contract file) -- never for a model-side/transport/API failure, which becomes
    a PredictionEnvelope with valid_prediction=False instead."""


def build_model_identifier(model: str, thinking: dict, reasoning_effort: str) -> str:
    """Deterministic, stable construction that includes the actual configuration used --
    never silently relies on API defaults. Extends the documented example
    ('deepseek:deepseek-flash:thinking-disabled') with the reasoning_effort level too,
    since thinking-state alone cannot distinguish "low" from "high" from "max" once
    thinking is enabled, and two configurations must never share one identifier."""
    thinking_state = "enabled" if thinking.get("type") == "enabled" else "disabled"
    return f"deepseek:{model}:thinking-{thinking_state}:effort-{reasoning_effort}"


def _load_contract(decision_type: str) -> dict:
    path = PROMPTS_DIR / f"{decision_type}.json"
    if not path.exists():
        raise DeepSeekAdapterError(f"no prompt contract for decision_type={decision_type!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def _render_user_content(rendered_prompt: Any) -> str:
    if isinstance(rendered_prompt, str):
        return rendered_prompt
    return json.dumps(rendered_prompt, sort_keys=True)


def build_request_body(
    decision_type: str, rendered_prompt: Any, allowed_output_values: list[str],
    model: str, thinking: dict, reasoning_effort: str,
) -> dict:
    """Builds the OpenAI-compatible chat-completions request body. The decision_question
    is the contract's own text, verbatim -- it carries all the real semantics, unmodified.
    The JSON transport instruction is appended as a separate sentence describing only how
    the answer must be shaped on the wire, never what is being asked."""
    contract = _load_contract(decision_type)
    transport_instruction = JSON_TRANSPORT_INSTRUCTION_TEMPLATE.format(
        values=", ".join(repr(v) for v in allowed_output_values)
    )
    system_content = f"{contract['decision_question']}\n\n{transport_instruction}"
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": _render_user_content(rendered_prompt)},
        ],
        "response_format": {"type": "json_object"},
        "thinking": dict(thinking),
        "reasoning_effort": reasoning_effort,
    }


def parse_decision_content(content: str, allowed_output_values: list[str]) -> tuple[str | None, str | None]:
    """Independently validates the model's raw text content against the JSON transport
    contract. Never trusts response_format=json_object alone, and never performs broad
    extraction of a JSON object embedded in surrounding prose -- if there is anything
    besides the JSON object itself, that is malformed output, not a repair opportunity.

    Returns (decision_value, error). Exactly one of the two is None."""
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None, "malformed_output: invalid_json"

    if not isinstance(parsed, dict):
        return None, "malformed_output: non_object"

    if "decision" not in parsed:
        return None, "malformed_output: missing_decision"

    if set(parsed.keys()) != {"decision"}:
        return None, "malformed_output: extra_keys"

    decision = parsed["decision"]
    if not isinstance(decision, str):
        return None, "malformed_output: decision_not_string"

    if decision not in allowed_output_values:
        return None, f"invalid_output: decision_not_allowed: {decision!r} not in {allowed_output_values}"

    return decision, None


class DeepSeekAdapter:
    """ModelAdapter implementation over an injectable HTTP transport callable:
    `transport(request_body: dict) -> dict`, returning the full parsed JSON response body
    (e.g. {"choices": [...], "usage": {...}}). `transport` may raise for any transport/API
    failure (timeout, non-2xx, connection error, auth failure) -- the adapter converts any
    such exception into a PredictionEnvelope, never a crash, and never retries."""

    def __init__(
        self, transport: Callable[[dict], dict],
        model: str = DEFAULT_MODEL, thinking: dict | None = None,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
    ):
        self.transport = transport
        self.model = model
        self.thinking = dict(thinking) if thinking is not None else dict(DEFAULT_THINKING)
        self.reasoning_effort = reasoning_effort
        self.model_identifier = build_model_identifier(self.model, self.thinking, self.reasoning_effort)

    def predict(self, decision_type: str, rendered_prompt: Any, allowed_output_values: list[str]) -> PredictionEnvelope:
        request_body = build_request_body(
            decision_type, rendered_prompt, allowed_output_values,
            self.model, self.thinking, self.reasoning_effort,
        )

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
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return PredictionEnvelope(
                predicted_value=None, valid_prediction=False,
                error="malformed_output: missing_choices_content",
                latency_ms=elapsed_ms, input_tokens=None, output_tokens=None,
                cache_read_tokens=None, cache_write_tokens=None,
                model_identifier=self.model_identifier, raw_response=raw_response,
            )

        usage = response.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        cache_read_tokens = usage.get("prompt_cache_hit_tokens")

        decision, error = parse_decision_content(content, allowed_output_values)
        valid = error is None

        return PredictionEnvelope(
            predicted_value=decision,
            valid_prediction=valid,
            error=error,
            latency_ms=elapsed_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=None,  # DeepSeek reports no cache-write concept at all
            model_identifier=self.model_identifier,
            # Never manufactured: DeepSeek's chat-completions response for an arbitrary
            # JSON decision exposes no directly supported, semantically valid class-
            # probability source (token logprobs are per-token, not per-class -- see the
            # Phase 4 DeepSeek design report). confidence/probability_distribution stay
            # None regardless of validity.
            confidence=None,
            probability_distribution=None,
            raw_response=raw_response,
        )
