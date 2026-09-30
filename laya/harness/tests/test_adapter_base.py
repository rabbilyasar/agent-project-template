#!/usr/bin/env python3
"""Self-tests for lib/adapter_base.py: PredictionEnvelope, the ModelAdapter protocol
shape, and build_canonical_result(). No Laya/GPU/network involved."""
from __future__ import annotations

from _load_lib import load_lib_module

adapter_base = load_lib_module("adapter_base.py", "adapter_base")


class _StubAdapter:
    """Minimal object satisfying ModelAdapter structurally -- proves the interface is
    sufficient and vendor-agnostic without importing anything Laya-specific."""

    model_identifier = "stub-model-v1"

    def predict(self, decision_type, rendered_prompt, allowed_output_values):
        return adapter_base.PredictionEnvelope(
            predicted_value=allowed_output_values[0], valid_prediction=True, error=None,
            latency_ms=1.0, input_tokens=10, output_tokens=0, cache_read_tokens=None,
            cache_write_tokens=None, model_identifier=self.model_identifier,
        )


def main() -> int:
    checks = []

    stub = _StubAdapter()
    envelope = stub.predict("trivial_vs_staged", {"task_description": "x"}, ["trivial", "staged"])
    checks.append(("a stub adapter can satisfy ModelAdapter structurally", isinstance(envelope, adapter_base.PredictionEnvelope)))
    checks.append(("stub predict() never received candidate_id/corpus fields",
                   set(_StubAdapter.predict.__code__.co_varnames[:4]) == {"self", "decision_type", "rendered_prompt", "allowed_output_values"}))

    checks.append(("PredictionEnvelope defaults confidence to None", adapter_base.PredictionEnvelope(
        predicted_value="a", valid_prediction=True, error=None, latency_ms=None,
        input_tokens=None, output_tokens=None, cache_read_tokens=None, cache_write_tokens=None,
        model_identifier="m",
    ).confidence is None))

    checks.append(("PredictionEnvelope is frozen (read-only)", True))
    try:
        envelope.predicted_value = "mutated"
        checks[-1] = ("PredictionEnvelope is frozen (read-only)", False)
    except Exception:
        pass

    result = adapter_base.build_canonical_result(
        "SYN-01", "trivial_vs_staged", "run-1", "0" * 64, envelope, timestamp="2026-01-01T00:00:00+00:00",
    )
    checks.append(("build_canonical_result carries candidate_id (orchestrator-owned, never from the envelope)", result["candidate_id"] == "SYN-01"))
    checks.append(("build_canonical_result carries run_id (orchestrator-owned)", result["run_id"] == "run-1"))
    checks.append(("build_canonical_result carries corpus_content_hash (orchestrator-owned)", result["corpus_content_hash"] == "0" * 64))
    checks.append(("build_canonical_result carries the envelope's model_identifier", result["model_identifier"] == "stub-model-v1"))
    checks.append(("build_canonical_result carries the envelope's predicted_value", result["predicted_value"] == "trivial"))
    checks.append(("build_canonical_result defaults timestamp when not given", "timestamp" in adapter_base.build_canonical_result(
        "SYN-02", "trivial_vs_staged", "run-1", "0" * 64, envelope,
    )))

    required_result_schema_fields = {
        "candidate_id", "decision_type", "run_id", "model_identifier", "predicted_value",
        "valid_prediction", "latency_ms", "error", "timestamp", "corpus_content_hash",
    }
    checks.append(("build_canonical_result output has every result_schema.json required field",
                   required_result_schema_fields <= set(result)))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  adapter_base checks failed: {failed}")
        return 1
    print(f"PASS  adapter_base: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
