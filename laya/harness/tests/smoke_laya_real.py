#!/usr/bin/env python3
"""Real-Laya integration smoke for lib/laya_adapter.py -- NOT part of run_all.sh.

Requires the actual `laya`/`torch` packages and a working CUDA (ROCm) device, e.g. the
already-validated environment at /home/rabbil/experiments/laya-smoke/.venv:

    /home/rabbil/experiments/laya-smoke/.venv/bin/python laya/harness/tests/smoke_laya_real.py

Uses one trivial synthetic decision (unrelated to any real corpus row, no corpus evidence)
to prove the adapter's wiring against the real checkpoint. No corpus rows, no evaluation
scoring, no aggregate report -- this is wiring verification only, never evaluation evidence.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from _module_loader import load_lib_module  # noqa: E402

laya_adapter = load_lib_module("laya_adapter.py", "laya_adapter")
serialize = load_lib_module("08_serialize_result.py", "serialize")

SYNTHETIC_STATE = "A shopper is choosing between two fruit baskets at a market stall."
SYNTHETIC_ALLOWED_VALUES = ["alpha", "beta"]
SYNTHETIC_CONTRACT_STANDIN = {
    "decision_question": "Which basket should the shopper pick, based only on the stated size?",
    "allowed_output_values": SYNTHETIC_ALLOWED_VALUES,
}


def main() -> int:
    checks = []
    captured_warnings = []

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        # 1. model loads under the configured CUDA environment
        import laya as laya_pkg  # noqa: F401  -- import here only to read __version__
        agent = laya_adapter.load_laya_agent("convaiinnovations/laya-typed-decisions", device="cuda")
        checks.append(("model loads under configured device=cuda", agent is not None))
        captured_warnings = [str(w.message) for w in caught]

    model_identifier = laya_adapter.build_model_identifier(laya_pkg.__version__, "convaiinnovations/laya-typed-decisions")
    adapter = laya_adapter.LayaAdapter(agent, model_identifier)

    # Monkeypatch the contract loader for this smoke only, so it never touches the real
    # laya/harness/prompts/*.json files or any real decision_type -- entirely synthetic.
    laya_adapter._load_contract = lambda decision_type: SYNTHETIC_CONTRACT_STANDIN

    # 2. one synthetic choice call works
    envelope = adapter.predict("synthetic_smoke_decision", SYNTHETIC_STATE, SYNTHETIC_ALLOWED_VALUES)
    checks.append(("predict() returned a PredictionEnvelope", envelope.__class__.__name__ == "PredictionEnvelope"))
    checks.append(("predicted_value is one of the allowed synthetic values", envelope.predicted_value in SYNTHETIC_ALLOWED_VALUES))
    checks.append(("valid_prediction is True for a clean synthetic call", envelope.valid_prediction is True))
    checks.append(("confidence (answer_confidence) is a float in [0,1]", envelope.confidence is not None and 0.0 <= envelope.confidence <= 1.0))
    checks.append(("probability_distribution covers both allowed values", set(envelope.probability_distribution) == set(SYNTHETIC_ALLOWED_VALUES)))
    checks.append(("input_tokens is a positive int", isinstance(envelope.input_tokens, int) and envelope.input_tokens > 0))
    checks.append(("output_tokens is the real reported 0, not None", envelope.output_tokens == 0))
    checks.append(("cache_read_tokens/cache_write_tokens remain None", envelope.cache_read_tokens is None and envelope.cache_write_tokens is None))
    checks.append(("model_identifier matches the constructed stable identifier", envelope.model_identifier == model_identifier))

    # 3 (folded into 2's checks above) + 4. canonical result validates against result_schema.json
    from adapter_base import build_canonical_result  # noqa: E402  (adapter_base already on sys.path via lib/)
    canonical = build_canonical_result("SMOKE-01", "synthetic_smoke_decision", "smoke-run-1", "0" * 64, envelope)
    schema_errors = serialize.validate_against_result_schema(canonical)
    checks.append(("canonical result validates against result_schema.json", schema_errors == []))

    # 5 + 6. predict_batch() on a tiny synthetic batch, ordering preserved
    states = [SYNTHETIC_STATE, "A different shopper picks between a large and a small crate."]
    batch_envelopes = adapter.predict_batch("synthetic_smoke_decision", states, SYNTHETIC_ALLOWED_VALUES)
    checks.append(("predict_batch returned one envelope per input", len(batch_envelopes) == len(states)))
    checks.append(("predict_batch results are all valid predictions", all(e.valid_prediction for e in batch_envelopes)))
    checks.append(("single predict() and predict_batch([same state]) agree on the first item",
                   batch_envelopes[0].predicted_value == adapter.predict("synthetic_smoke_decision", states[0], SYNTHETIC_ALLOWED_VALUES).predicted_value))

    # 7. load-time checkpoint warning captured/reported, if any -- never suppressed, tuned, or acted on
    print("--- load-time warnings captured (reported only, not modified) ---")
    if captured_warnings:
        for w in captured_warnings:
            print(f"  WARNING: {w}")
    else:
        print("  (none captured this run)")

    failed = [name for name, ok in checks if not ok]
    print()
    if failed:
        print(f"FAIL  real-Laya smoke checks failed: {failed}")
        return 1
    print(f"PASS  real-Laya smoke: {len(checks)} checks, {len(captured_warnings)} load-time warning(s) captured")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
