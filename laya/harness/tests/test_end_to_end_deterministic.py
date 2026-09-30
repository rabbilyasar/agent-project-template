#!/usr/bin/env python3
"""End-to-end, fully model-free self-test of the Slice 2 pipeline:

corpus -> loader -> leakage preflight -> deterministic prefilter -> canonical result
       -> scoring -> aggregation -> serialization

Proves the pipeline's contracts connect correctly. Uses only the real corpus (read-only,
for the loader/preflight/prefilter stages, since those are the components meant to run
against it) and, for scoring/aggregation/serialization, a small set of synthetic canonical
results so the scored outcome is a known, checkable quantity rather than whatever the
frozen deterministic rule happens to produce against real DP-22 rows today. Zero model or
API calls anywhere in this test.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from _fixtures import canonical_result, dp22_row
from _load_lib import load_lib_module

load_corpus = load_lib_module("01_load_corpus.py", "load_corpus")
preflight = load_lib_module("02_leakage_preflight.py", "leakage_preflight")
prefilter = load_lib_module("04_deterministic_prefilter.py", "prefilter")
aggregate = load_lib_module("07_aggregate_report.py", "aggregate")
serialize = load_lib_module("08_serialize_result.py", "serialize")


def main() -> int:
    checks = []

    # 1. corpus -> loader
    rows, corpus_hash = load_corpus.load_corpus()
    checks.append(("stage 1: loader returns all 36 real corpus rows", len(rows) == 36))
    dp22_rows = [r for r in rows if r.decision_type == "agent_verification_applicable"]

    # 2. loader -> leakage preflight (every real DP-22 row's model_facing_input)
    preflight_failures = []
    for row in dp22_rows:
        rendered = str(load_corpus.model_facing_payload(row))
        result = preflight.check_leakage(rendered, row.raw)
        if not result.passed:
            preflight_failures.append((row.candidate_id, result.hard_failures))
    checks.append(("stage 2: leakage preflight passes for all real DP-22 rows", not preflight_failures))

    # 3. leakage preflight -> deterministic prefilter -> canonical result (real DP-22 rows)
    run_id = "e2e-test-run"
    real_results = []
    for row in dp22_rows:
        out = prefilter.deterministic_prefilter(row.decision_type, load_corpus.model_facing_payload(row))
        real_results.append(prefilter.build_canonical_result(
            row.candidate_id, row.decision_type, run_id, corpus_hash,
            ["applicable", "not_applicable"], out,
        ))
    checks.append(("stage 3: one canonical result per real DP-22 row", len(real_results) == len(dp22_rows)))
    checks.append(("stage 3: canonical results carry the loader's own corpus_content_hash", all(r["corpus_content_hash"] == corpus_hash for r in real_results)))
    checks.append(("stage 3: deferred rows are valid_prediction=False, not coerced", all(r["valid_prediction"] is False for r in real_results if r["predicted_value"] is None)))

    # 4-6. canonical result -> scoring -> aggregation, using a small synthetic set with a
    # known, checkable outcome (independent of what the frozen rule happens to score today).
    synthetic_rows = {
        "E2E-D1": dp22_row("E2E-D1", "deterministic_prefilter_validation", "applicable"),
        "E2E-D2": dp22_row("E2E-D2", "deterministic_prefilter_validation", "not_applicable"),
        "E2E-S1": dp22_row("E2E-S1", "system1_judgment", "applicable"),
        "E2E-S2": dp22_row("E2E-S2", "system1_judgment", "applicable"),
    }
    synthetic_results = [
        canonical_result("E2E-D1", "agent_verification_applicable", "applicable", run_id=run_id, corpus_hash=corpus_hash),
        canonical_result("E2E-D2", "agent_verification_applicable", "applicable", run_id=run_id, corpus_hash=corpus_hash),  # incorrect
        canonical_result("E2E-S1", "agent_verification_applicable", "applicable", run_id=run_id, corpus_hash=corpus_hash),
        canonical_result("E2E-S2", "agent_verification_applicable", "not_applicable", run_id=run_id, corpus_hash=corpus_hash),  # incorrect
    ]
    report = aggregate.build_report(
        "agent_verification_applicable", synthetic_results, synthetic_rows, run_id, corpus_hash,
        "1.0", prefilter.MODEL_IDENTIFIER,
    )
    checks.append(("stage 4-5: scoring flows into aggregation with correct per-partition accuracy",
                   report["blocks"]["deterministic_prefilter_validation"]["accuracy"] == 0.5
                   and report["blocks"]["system1_judgment"]["accuracy"] == 0.5))
    checks.append(("stage 4-5: partitions are never merged end-to-end either", "overall" not in report))
    checks.append(("stage 4-5: aggregation preserves the corpus_content_hash through the whole pipeline",
                   report["corpus_content_hash"] == corpus_hash))

    # 7. aggregation/results -> serialization
    all_predictions = real_results + synthetic_results
    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "e2e-results.jsonl"
        serialize.write_results_jsonl(all_predictions, out_path)
        read_back = serialize.read_results_jsonl(out_path)
        checks.append(("stage 6: every canonical result serializes and round-trips", read_back == all_predictions))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  end-to-end deterministic pipeline checks failed: {failed}")
        if preflight_failures:
            print(f"      preflight failures: {preflight_failures}")
        return 1
    print(f"PASS  end-to-end deterministic pipeline: {len(checks)} checks, zero model/API calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
