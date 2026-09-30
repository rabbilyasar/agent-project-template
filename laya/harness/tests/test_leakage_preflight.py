#!/usr/bin/env python3
"""Self-tests for lib/02_leakage_preflight.py, against synthetic rendered-prompt fixtures
(never the real corpus data) plus one regression guard against the real corpus."""
from __future__ import annotations

from pathlib import Path

from _load_lib import load_lib_module

preflight = load_lib_module("02_leakage_preflight.py", "leakage_preflight")
load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")

BASE_ROW = {
    "candidate_id": "ZEUS-DP22-03",
    "decision_type": "agent_verification_applicable",
    "ground_truth_label": "applicable",
    "ground_truth_evidence": {
        "quote": "the query-ordering change was verified by re-running the affected report end to end",
        "citation": "zeus:session-log:line-412",
        "verification_method": "manual",
    },
    "normative_basis": None,
    "empirical_basis": None,
    "leakage_check": {"passed": True, "note": "reviewed for post-decision leakage during hardening"},
}


def main() -> int:
    checks = []

    clean_prompt = "Files touched: reports/export.py. Change description: adjust a report's sort order."
    result = preflight.check_leakage(clean_prompt, BASE_ROW)
    checks.append(("clean prompt with no forbidden content passes", result.passed and not result.hard_failures))

    quote_leak_prompt = clean_prompt + " " + BASE_ROW["ground_truth_evidence"]["quote"]
    result = preflight.check_leakage(quote_leak_prompt, BASE_ROW)
    checks.append(("verbatim ground_truth_evidence.quote is a hard failure", not result.passed))

    id_leak_prompt = clean_prompt + " (see ZEUS-DP22-03)"
    result = preflight.check_leakage(id_leak_prompt, BASE_ROW)
    checks.append(("candidate_id in prompt is a hard failure even though it's short", not result.passed))

    basis_row = dict(BASE_ROW, normative_basis="a sufficiently long normative basis sentence for exact-copy detection")
    basis_leak_prompt = clean_prompt + " " + basis_row["normative_basis"]
    result = preflight.check_leakage(basis_leak_prompt, basis_row)
    checks.append(("verbatim normative_basis is a hard failure", not result.passed))

    dp16_row = dict(BASE_ROW, decision_type="documented_limitation_vs_defect", ground_truth_label="deliberate")
    label_leak_prompt = clean_prompt + " this behavior is deliberate per the excerpt above"
    result = preflight.check_leakage(label_leak_prompt, dp16_row)
    checks.append(("documented_limitation_vs_defect is exempt from its own label-token check", result.passed))

    non_exempt_row = dict(BASE_ROW, decision_type="human_acceptance_required", normative_label="sufficient_without")
    label_leak_prompt2 = clean_prompt + " acceptance is sufficient without further review"
    result = preflight.check_leakage(label_leak_prompt2, non_exempt_row)
    checks.append(("non-exempt decision type hard-fails on its own literal label token", not result.passed))

    paraphrase_row = dict(BASE_ROW, normative_basis=(
        "the deployment pipeline automatically runs the full regression suite before promoting the build"
    ))
    paraphrase_prompt = (
        "Change description: full regression suite runs automatically; the build is promoted "
        "only after the deployment pipeline confirms results."
    )
    result = preflight.check_leakage(paraphrase_prompt, paraphrase_row)
    checks.append(("high-overlap paraphrase is a warning, not a hard failure", result.passed and len(result.warnings) > 0))

    try:
        preflight.assert_no_leakage(quote_leak_prompt, BASE_ROW)
        checks.append(("assert_no_leakage raises LeakagePreflightFailure on hard failure", False))
    except preflight.LeakagePreflightFailure:
        checks.append(("assert_no_leakage raises LeakagePreflightFailure on hard failure", True))

    ok_result = preflight.assert_no_leakage(clean_prompt, BASE_ROW)
    checks.append(("assert_no_leakage returns a PreflightResult on success", isinstance(ok_result, preflight.PreflightResult)))

    # Regression guard: the real, already-hardened corpus's own model_facing_input must
    # stay leak-free under this preflight (read-only; the corpus itself is not modified).
    rows, _ = load_corpus_mod.load_corpus()
    real_failures = []
    for row in rows:
        rendered = str(load_corpus_mod.model_facing_payload(row))
        r = preflight.check_leakage(rendered, row.raw)
        if not r.passed:
            real_failures.append((row.candidate_id, r.hard_failures))
    checks.append(("real corpus model_facing_input has zero hard leakage failures", not real_failures))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  leakage preflight checks failed: {failed}")
        if real_failures:
            print(f"      real corpus failures: {real_failures}")
        return 1
    print(f"PASS  leakage preflight: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
