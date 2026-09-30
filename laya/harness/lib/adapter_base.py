"""Vendor-neutral adapter boundary for Phase 4.2 model-quality evaluation.

    ModelAdapter.predict(...)
            -> PredictionEnvelope
            -> (orchestrator) build_canonical_result(...)
            -> canonical result (laya/schema/result_schema.json)

An adapter receives only decision_type, an already-rendered model-facing payload, and
allowed_output_values -- never candidate_id, the corpus row, ground truth, corpus_partition,
evidence, inclusion_status, ambiguity_tier, or any other corpus-provenance/evaluation
metadata. It must never raise for a model-side failure (timeout, malformed output, rate
limit, inference exception); those become a PredictionEnvelope with valid_prediction=False
and a populated `error` instead. It may raise only for a programming/contract error (an
unrecognized decision_type, a missing prompt contract file).

Identity and run metadata (candidate_id, run_id, corpus_content_hash) are owned exclusively
by the orchestrator (not implemented in this slice) and merged in with an envelope by
build_canonical_result() below -- this is the only place the two are ever combined.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PredictionEnvelope:
    predicted_value: str | None
    valid_prediction: bool
    error: str | None
    latency_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    model_identifier: str
    confidence: float | None = None
    probability_distribution: dict | None = None
    raw_response: Any = None


class ModelAdapter(Protocol):
    model_identifier: str

    def predict(
        self, decision_type: str, rendered_prompt: Any, allowed_output_values: list[str],
    ) -> PredictionEnvelope:
        """rendered_prompt is whatever the render step already produced for this row
        (a string, dict, or list) -- the adapter never receives the corpus row itself."""
        ...


def build_canonical_result(
    candidate_id: str, decision_type: str, run_id: str, corpus_content_hash: str,
    envelope: PredictionEnvelope, timestamp: str | None = None,
) -> dict:
    """Merges orchestrator-owned identity/run metadata with an adapter's model-side
    envelope into the canonical result_schema.json shape. The only place candidate_id and
    an envelope are ever combined."""
    from datetime import datetime, timezone

    return {
        "candidate_id": candidate_id,
        "decision_type": decision_type,
        "run_id": run_id,
        "model_identifier": envelope.model_identifier,
        "predicted_value": envelope.predicted_value,
        "valid_prediction": envelope.valid_prediction,
        "confidence": envelope.confidence,
        "probability_distribution": envelope.probability_distribution,
        "latency_ms": envelope.latency_ms,
        "input_tokens": envelope.input_tokens,
        "output_tokens": envelope.output_tokens,
        "cache_read_tokens": envelope.cache_read_tokens,
        "cache_write_tokens": envelope.cache_write_tokens,
        "error": envelope.error,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "corpus_content_hash": corpus_content_hash,
        "raw_response": envelope.raw_response,
    }
