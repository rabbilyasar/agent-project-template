#!/usr/bin/env python3
"""Self-tests for lib/06_score.py, against synthetic fixtures only."""
from __future__ import annotations

from _fixtures import canonical_result, dp11_row, dp16_row, dp22_row, dp23_row
from _load_lib import load_lib_module

score_mod = load_lib_module("06_score.py", "score")


def main() -> int:
    checks = []

    rows = {
        "A": dp22_row("A", "deterministic_prefilter_validation", "applicable"),
        "B": dp22_row("B", "deterministic_prefilter_validation", "not_applicable"),
        "C": dp22_row("C", "deterministic_prefilter_validation", "applicable"),
    }
    results = [
        canonical_result("A", "agent_verification_applicable", "applicable", valid=True),   # correct
        canonical_result("B", "agent_verification_applicable", "applicable", valid=True),   # incorrect
        canonical_result("C", "agent_verification_applicable", "maybe", valid=False),        # invalid
    ]
    scored = score_mod.score_batch(results, rows, "agent_verification_applicable")
    checks.append(("correct prediction is classified correct", scored[0].correct is True))
    checks.append(("incorrect prediction is classified incorrect", scored[1].correct is False))
    checks.append(("invalid prediction has correct=None, not False", scored[2].correct is None))

    summary = score_mod.summarize(scored)
    checks.append(("coverage = valid/n", summary["coverage"] == 2 / 3))
    checks.append(("accuracy computed only over valid predictions", summary["accuracy"] == 0.5))
    checks.append(("per_class_counts reflects ground truth distribution", summary["per_class_counts"] == {"applicable": 2, "not_applicable": 1}))
    checks.append(("confusion_matrix counts the incorrect prediction", summary["confusion_matrix"]["not_applicable"]["applicable"] == 1))
    checks.append(("confusion_matrix counts the correct prediction", summary["confusion_matrix"]["applicable"]["applicable"] == 1))
    checks.append(("invalid prediction is excluded from the confusion matrix", sum(v for d in summary["confusion_matrix"].values() for v in d.values()) == 2))

    # DP-11 must never be scored for accuracy.
    dp11_rows = {"X": dp11_row("X", "staged")}
    try:
        score_mod.score_batch([canonical_result("X", "trivial_vs_staged", "staged")], dp11_rows, "trivial_vs_staged")
        checks.append(("trivial_vs_staged raises ScoringConfigError rather than producing accuracy", False))
    except score_mod.ScoringConfigError:
        checks.append(("trivial_vs_staged raises ScoringConfigError rather than producing accuracy", True))

    # DP-22 partitions must never be scored together as one batch by accident -- scoring
    # a mixed batch doesn't itself raise (partition separation is the aggregator's job), but
    # each ScoredPrediction still carries its own row's ground truth correctly.
    mixed_rows = {
        "P1": dp22_row("P1", "deterministic_prefilter_validation", "applicable"),
        "P2": dp22_row("P2", "system1_judgment", "not_applicable"),
    }
    mixed_results = [
        canonical_result("P1", "agent_verification_applicable", "applicable"),
        canonical_result("P2", "agent_verification_applicable", "not_applicable"),
    ]
    mixed_scored = score_mod.score_batch(mixed_results, mixed_rows, "agent_verification_applicable")
    checks.append(("scoring resolves each row's own ground truth regardless of partition",
                   {s.candidate_id: s.ground_truth for s in mixed_scored} == {"P1": "applicable", "P2": "not_applicable"}))

    # DP-16 polarity blocks: scoring itself is polarity-agnostic; the aggregator keeps blocks
    # separate. Confirm score_batch can be called per-polarity-filtered subset cleanly.
    dp16_rows = {
        "PM": dp16_row("PM", "positive_match", "deliberate"),
        "AB": dp16_row("AB", "absence_based", "defect"),
    }
    pm_scored = score_mod.score_batch([canonical_result("PM", "documented_limitation_vs_defect", "deliberate")], dp16_rows, "documented_limitation_vs_defect")
    ab_scored = score_mod.score_batch([canonical_result("AB", "documented_limitation_vs_defect", "deliberate")], dp16_rows, "documented_limitation_vs_defect")
    checks.append(("DP-16 positive_match block scores independently", pm_scored[0].correct is True))
    checks.append(("DP-16 absence_based block scores independently (and can disagree)", ab_scored[0].correct is False))

    # DP-23 must score ONLY against normative_label.
    dp23_rows = {"N": dp23_row("N", normative_label="required", empirical_label="bare_acknowledgment", relationship="diverge")}
    dp23_scored = score_mod.score_batch([canonical_result("N", "human_acceptance_required", "required")], dp23_rows, "human_acceptance_required")
    checks.append(("DP-23 scores against normative_label even when empirical_label diverges", dp23_scored[0].correct is True))

    try:
        score_mod.score_one(canonical_result("N", "human_acceptance_required", "bare_acknowledgment"), dp23_rows["N"], "human_acceptance_required", target_field="empirical_label")
        checks.append(("accidental empirical-label scoring target raises ScoringConfigError", False))
    except score_mod.ScoringConfigError:
        checks.append(("accidental empirical-label scoring target raises ScoringConfigError", True))

    try:
        score_mod.score_one(canonical_result("N", "human_acceptance_required", "required"), dp23_rows["N"], "human_acceptance_required", target_field="ground_truth_label")
        checks.append(("accidental ground_truth_label target for DP-23 raises ScoringConfigError", False))
    except score_mod.ScoringConfigError:
        checks.append(("accidental ground_truth_label target for DP-23 raises ScoringConfigError", True))

    try:
        score_mod.score_one(
            canonical_result("A", "agent_verification_applicable", "applicable"), rows["A"],
            "agent_verification_applicable", target_field="normative_label",
        )
        checks.append(("mismatched decision_type/target_field combination fails loudly", False))
    except score_mod.ScoringConfigError:
        checks.append(("mismatched decision_type/target_field combination fails loudly", True))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  scoring checks failed: {failed}")
        return 1
    print(f"PASS  scoring: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
