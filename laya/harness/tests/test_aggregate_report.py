#!/usr/bin/env python3
"""Self-tests for lib/07_aggregate_report.py, against synthetic fixtures only."""
from __future__ import annotations

import json

from _fixtures import canonical_result, dp11_row, dp16_row, dp22_row, dp23_row
from _load_lib import load_lib_module

aggregate = load_lib_module("07_aggregate_report.py", "aggregate")

NO_RANKING_TOKENS = ("winner", "ranking", "rank", "best_model", "comparison")


def _no_ranking_language(obj) -> bool:
    blob = json.dumps(obj).lower()
    return not any(tok in blob for tok in NO_RANKING_TOKENS)


def main() -> int:
    checks = []

    # --- DP-11: never scored, not_scored explicit, no accuracy value ---
    dp11_results = [
        canonical_result("T1", "trivial_vs_staged", "trivial"),
        canonical_result("T2", "trivial_vs_staged", "staged"),
    ]
    dp11_report = aggregate.build_report("trivial_vs_staged", dp11_results, {}, "run-1", "hash", "1.0", "m1")
    checks.append(("DP-11 report sets not_scored=True", dp11_report["not_scored"] is True))
    checks.append(("DP-11 report has no accuracy value", dp11_report["accuracy"] is None))
    checks.append(("DP-11 report gives a reason", bool(dp11_report.get("reason"))))
    checks.append(("DP-11 report n is correct", dp11_report["n"] == 2))

    # --- DP-22: two never-merged blocks, System-1 sample_size_warning ---
    dp22_rows = {
        "D1": dp22_row("D1", "deterministic_prefilter_validation", "applicable"),
        "D2": dp22_row("D2", "deterministic_prefilter_validation", "applicable"),
        "S1": dp22_row("S1", "system1_judgment", "applicable"),
        "S2": dp22_row("S2", "system1_judgment", "not_applicable"),
    }
    dp22_results = [
        canonical_result("D1", "agent_verification_applicable", "applicable"),
        canonical_result("D2", "agent_verification_applicable", "not_applicable"),
        canonical_result("S1", "agent_verification_applicable", "applicable"),
        canonical_result("S2", "agent_verification_applicable", "applicable"),
    ]
    dp22_report = aggregate.build_report("agent_verification_applicable", dp22_results, dp22_rows, "run-2", "hash", "1.0", "m1")
    checks.append(("DP-22 report has exactly the two approved partition blocks",
                   set(dp22_report["blocks"]) == {"deterministic_prefilter_validation", "system1_judgment"}))
    checks.append(("DP-22 report has no combined/overall key", "overall" not in dp22_report))
    checks.append(("DP-22 prefilter-validation block counts only its own 2 rows", dp22_report["blocks"]["deterministic_prefilter_validation"]["n"] == 2))
    checks.append(("DP-22 system1_judgment block counts only its own 2 rows (never merged)", dp22_report["blocks"]["system1_judgment"]["n"] == 2))
    checks.append(("DP-22 system1_judgment block has sample_size_warning=True", dp22_report["blocks"]["system1_judgment"]["sample_size_warning"] is True))
    checks.append(("DP-22 prefilter-validation block has no sample_size_warning", "sample_size_warning" not in dp22_report["blocks"]["deterministic_prefilter_validation"]))
    checks.append(("DP-22 report emits no ranking/winner language", _no_ranking_language(dp22_report)))

    # --- DP-16: overall + positive_match + absence_based, kept separate ---
    dp16_rows = {
        "PM1": dp16_row("PM1", "positive_match", "deliberate"),
        "PM2": dp16_row("PM2", "positive_match", "deliberate"),
        "AB1": dp16_row("AB1", "absence_based", "defect"),
    }
    dp16_results = [
        canonical_result("PM1", "documented_limitation_vs_defect", "deliberate"),
        canonical_result("PM2", "documented_limitation_vs_defect", "defect"),
        canonical_result("AB1", "documented_limitation_vs_defect", "defect"),
    ]
    dp16_report = aggregate.build_report("documented_limitation_vs_defect", dp16_results, dp16_rows, "run-3", "hash", "1.0", "m1")
    checks.append(("DP-16 report has overall, positive_match, absence_based blocks",
                   set(dp16_report["blocks"]) == {"overall", "positive_match", "absence_based"}))
    checks.append(("DP-16 overall block covers all 3 rows", dp16_report["blocks"]["overall"]["n"] == 3))
    checks.append(("DP-16 positive_match block is scored independently of absence_based",
                   dp16_report["blocks"]["positive_match"]["accuracy"] == 0.5))
    checks.append(("DP-16 absence_based block is scored independently of positive_match",
                   dp16_report["blocks"]["absence_based"]["accuracy"] == 1.0))

    # --- DP-23: scored only against normative_label ---
    dp23_rows = {"N1": dp23_row("N1", normative_label="required", empirical_label="bare_acknowledgment", relationship="diverge")}
    dp23_results = [canonical_result("N1", "human_acceptance_required", "required")]
    dp23_report = aggregate.build_report("human_acceptance_required", dp23_results, dp23_rows, "run-4", "hash", "1.0", "m1")
    checks.append(("DP-23 report scores against normative_label despite empirical divergence", dp23_report["accuracy"] == 1.0))

    # Metadata plumbing.
    checks.append(("aggregate report carries run_id through", dp22_report["run_id"] == "run-2"))
    checks.append(("aggregate report carries corpus_content_hash through", dp22_report["corpus_content_hash"] == "hash"))
    checks.append(("aggregate report carries schema_version through", dp22_report["schema_version"] == "1.0"))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  aggregation checks failed: {failed}")
        return 1
    print(f"PASS  aggregation: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
