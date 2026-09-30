"""Laya System-1 ModelAdapter implementation, over the locally installed `laya` package
(typed-decision classification -- not text generation, not an HTTP API).

This module never imports `torch` or `laya` at module scope, and LayaAdapter itself never
imports them at all -- it only calls methods (`predict`/`predict_batch`) on whatever
`agent` object it is constructed with, so model-free tests can pass a plain stub with no
Laya/GPU dependency. `load_laya_agent()` is the one function that lazily imports `torch`/
`laya`, and is only ever called by a real-Laya smoke script, never by a model-free test.

Reuses the existing prompt contracts (laya/harness/prompts/*.json) as the sole source of
decision_question/allowed_output_values -- see build_questions() for exactly what is (and
is not) synthesized beyond that, and why.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from adapter_base import PredictionEnvelope

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

MODEL_IDENTIFIER_TEMPLATE = "laya:{version}:{model_id}"

# DP-22 is the only decision_type with a frozen deterministic rule (04_deterministic_
# prefilter.py). A row is eligible for Laya only if no deterministic rule claims it --
# i.e. every non-DP-22 decision_type unconditionally, and DP-22 rows only when their
# corpus_partition is exactly "system1_judgment". This mirrors, in one small tested
# predicate, the routing policy already stated across the Phase 4 design -- it is not a
# new architectural decision, and it is not an orchestrator.
_DP22_TYPE = "agent_verification_applicable"
_DP22_ELIGIBLE_PARTITION = "system1_judgment"


class LayaAdapterError(Exception):
    """Raised only for a programming/contract error (unknown decision_type, missing
    prompt contract file, misconfigured device) -- never for a model-side/runtime
    failure, which becomes a PredictionEnvelope with valid_prediction=False instead."""


def is_eligible_for_laya(decision_type: str, corpus_partition: str | None) -> bool:
    """Pure routing predicate. DP-22 rows outside the system1_judgment partition (the
    deterministic_prefilter_validation six, and the excluded RP-DP22-01) are NOT eligible
    -- they must never reach Laya, per the existing DP-22 partition policy."""
    if decision_type != _DP22_TYPE:
        return True
    return corpus_partition == _DP22_ELIGIBLE_PARTITION


def _load_contract(decision_type: str) -> dict:
    path = PROMPTS_DIR / f"{decision_type}.json"
    if not path.exists():
        raise LayaAdapterError(f"no prompt contract for decision_type={decision_type!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_questions(contract: dict) -> dict:
    """Builds the single Laya `choice` question this contract's decision maps onto.

    `instructions` is the contract's decision_question, verbatim -- it carries all of the
    real distinguishing semantics, unmodified. Laya's `choice` type additionally requires
    some text per allowed value under `criteria`; no prompt contract carries per-option
    descriptive prose (only a flat allowed_output_values list), and contracts are not to be
    modified or given a second format, so each option's criteria text is synthesized as a
    literal restatement of that one value's own name. This adds no semantic content beyond
    naming the option -- the actual decision semantics remain entirely and only whatever
    `instructions` (== decision_question) already states, so the original task is not
    rewritten or made easier for Laya.
    """
    allowed = contract["allowed_output_values"]
    return {
        "decision": {
            "type": "choice",
            "instructions": contract["decision_question"],
            "criteria": {value: f"The answer to the decision question is {value!r}." for value in allowed},
        }
    }


def require_device_available(device: str, is_available: bool) -> None:
    """Pure, torch-independent policy: if the configured device is 'cuda' and it is not
    available, fail clearly. Never silently falls back to a different device -- the
    caller (load_laya_agent) is the only place that supplies the real `is_available`
    value, so this function itself is fully unit-testable without torch installed."""
    if device == "cuda" and not is_available:
        raise LayaAdapterError(
            "configured device 'cuda' is not available -- refusing to silently fall back to CPU"
        )


def load_laya_agent(model_id_or_path: str = "convaiinnovations/laya-typed-decisions", device: str = "cuda"):
    """Loads the real Laya agent for the given device. Only ever called by a real-Laya
    smoke script -- model-free tests never call this, so they never require torch/laya."""
    import torch

    require_device_available(device, torch.cuda.is_available())
    import laya

    return laya.load(model_id_or_path, device=device)


def build_model_identifier(laya_version: str, model_id: str) -> str:
    return MODEL_IDENTIFIER_TEMPLATE.format(version=laya_version, model_id=model_id)


class LayaAdapter:
    """ModelAdapter implementation over an already-loaded Laya agent-like object (duck
    typed: anything exposing .predict(state, questions) and .predict_batch(states,
    questions, batch_size=, sort_by_length=) works, including a test stub)."""

    def __init__(self, agent, model_identifier: str):
        self.agent = agent
        self.model_identifier = model_identifier

    def predict(self, decision_type: str, rendered_prompt, allowed_output_values: list[str]) -> PredictionEnvelope:
        contract = _load_contract(decision_type)
        questions = build_questions(contract)
        t0 = time.perf_counter()
        try:
            raw = self.agent.predict(rendered_prompt, questions)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return PredictionEnvelope(
                predicted_value=None, valid_prediction=False,
                error=f"inference_exception: {type(e).__name__}: {e}",
                latency_ms=elapsed_ms, input_tokens=None, output_tokens=None,
                cache_read_tokens=None, cache_write_tokens=None,
                model_identifier=self.model_identifier, raw_response=None,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        return self._envelope_from_result(raw, allowed_output_values, latency_ms=elapsed_ms)

    def predict_batch(
        self, decision_type: str, rendered_prompts: list, allowed_output_values: list[str],
    ) -> list[PredictionEnvelope]:
        """Laya-specific batch path (predict_batch's `questions` argument is shared across
        the whole call, so every item here must be the same decision_type -- callers must
        group by decision_type before calling this). Preserves input order, per Laya's own
        documented guarantee. batch_size=None and sort_by_length=False are fixed, not
        configurable here, to avoid trading reproducibility for throughput at this corpus's
        scale. A batch-level failure marks every item in the batch failed with the same
        error, since a shared forward pass cannot be attributed to one row without evidence
        -- and batch-total latency is recorded only in raw_response, never divided by
        batch size and reported as though it were an individually measured latency."""
        contract = _load_contract(decision_type)
        questions = build_questions(contract)
        states = list(rendered_prompts)
        t0 = time.perf_counter()
        try:
            raw_results = self.agent.predict_batch(states, questions, batch_size=None, sort_by_length=False)
        except Exception as e:
            batch_elapsed_ms = (time.perf_counter() - t0) * 1000
            error = f"batch_failed: {type(e).__name__}: {e}"
            return [
                PredictionEnvelope(
                    predicted_value=None, valid_prediction=False, error=error,
                    latency_ms=None, input_tokens=None, output_tokens=None,
                    cache_read_tokens=None, cache_write_tokens=None,
                    model_identifier=self.model_identifier,
                    raw_response={"batch_elapsed_ms": batch_elapsed_ms},
                )
                for _ in states
            ]
        batch_elapsed_ms = (time.perf_counter() - t0) * 1000
        if len(raw_results) != len(states):
            error = f"malformed_output: predict_batch returned {len(raw_results)} results for {len(states)} inputs"
            return [
                PredictionEnvelope(
                    predicted_value=None, valid_prediction=False, error=error,
                    latency_ms=None, input_tokens=None, output_tokens=None,
                    cache_read_tokens=None, cache_write_tokens=None,
                    model_identifier=self.model_identifier,
                    raw_response={"batch_elapsed_ms": batch_elapsed_ms},
                )
                for _ in states
            ]
        return [
            self._envelope_from_result(raw, allowed_output_values, latency_ms=None, batch_elapsed_ms=batch_elapsed_ms)
            for raw in raw_results
        ]

    def _envelope_from_result(
        self, raw: dict, allowed_output_values: list[str], latency_ms, batch_elapsed_ms=None,
    ) -> PredictionEnvelope:
        raw_response = dict(raw) if isinstance(raw, dict) else {"value": raw}
        if batch_elapsed_ms is not None:
            raw_response = {"batch_elapsed_ms": batch_elapsed_ms, **raw_response}

        try:
            answer = raw["answers"]["decision"]
            usage = raw.get("usage") or {}
        except (KeyError, TypeError, AttributeError):
            return PredictionEnvelope(
                predicted_value=None, valid_prediction=False,
                error="malformed_output: missing answers.decision",
                latency_ms=latency_ms, input_tokens=None, output_tokens=None,
                cache_read_tokens=None, cache_write_tokens=None,
                model_identifier=self.model_identifier, raw_response=raw_response,
            )

        predicted_value = answer.get("choice") if isinstance(answer, dict) else None
        valid = predicted_value in allowed_output_values

        return PredictionEnvelope(
            predicted_value=predicted_value if valid else None,
            valid_prediction=valid,
            error=None if valid else f"invalid_output: {predicted_value!r} not in {allowed_output_values}",
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            cache_read_tokens=None,
            cache_write_tokens=None,
            model_identifier=self.model_identifier,
            # answer_confidence, never Laya's own entropy-derived `confidence` -- see
            # laya/harness/lib/05_calibration.py's identical "never entropy-based" rule.
            confidence=answer.get("answer_confidence") if valid else None,
            probability_distribution=answer.get("probabilities") if valid else None,
            raw_response=raw_response,
        )
