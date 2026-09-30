#!/usr/bin/env python3
"""Stage 6: model-independent scoring.

Accepts canonical result objects (laya/schema/result_schema.json) and corpus ground truth
-- never raw adapter responses, never raw_response -- so scoring behaves identically
regardless of which system (deterministic rule, Claude, Laya, JEV) produced a prediction.

Encodes the decision-specific rules approved for Phase 4.2:
- trivial_vs_staged is NEVER scored (see NOT_SCORED_DECISION_TYPES).
- human_acceptance_required is scored ONLY against normative_label, never empirical_label
  or ground_truth_label.
- agent_verification_applicable and documented_limitation_vs_defect are scored against
  ground_truth_label.
Partition/polarity separation (DP-22's two partitions, DP-16's evidence_polarity blocks)
is enforced by the aggregation stage, which calls this module once per block -- scoring
itself only guarantees the target-field rule for a single batch.
"""
from __future__ import annotations

from dataclasses import dataclass

NOT_SCORED_DECISION_TYPES = {"trivial_vs_staged"}

TARGET_FIELD_BY_DECISION_TYPE = {
    "agent_verification_applicable": "ground_truth_label",
    "documented_limitation_vs_defect": "ground_truth_label",
    "human_acceptance_required": "normative_label",
}

# Fields that must never be used as the scoring target for a given decision_type, even if
# requested explicitly -- a hard assertion against an accidental target mismatch.
FORBIDDEN_TARGET_FIELDS = {
    "human_acceptance_required": {"empirical_label", "ground_truth_label"},
}


class ScoringConfigError(Exception):
    """Raised when scoring is asked to target a field that is not the approved
    ground-truth target for a decision_type, or when a not-scored decision_type is scored
    anyway."""


@dataclass(frozen=True)
class ScoredPrediction:
    candidate_id: str
    predicted_value: str | None
    valid_prediction: bool
    ground_truth: str | None
    correct: bool | None  # None when not comparable (invalid prediction or missing ground truth)


def resolve_target_field(decision_type: str, requested_field: str | None = None) -> str:
    if decision_type in NOT_SCORED_DECISION_TYPES:
        raise ScoringConfigError(
            f"{decision_type} must never be scored for accuracy (not_scored=true) -- "
            f"see NOT_SCORED_DECISION_TYPES"
        )
    expected = TARGET_FIELD_BY_DECISION_TYPE.get(decision_type)
    if expected is None:
        raise ScoringConfigError(f"no approved ground-truth target field for decision_type={decision_type!r}")
    field = requested_field or expected
    if field != expected:
        raise ScoringConfigError(
            f"{decision_type} must be scored against {expected!r}, not {field!r} -- "
            f"refusing an accidental scoring-target mismatch"
        )
    forbidden = FORBIDDEN_TARGET_FIELDS.get(decision_type, set())
    if field in forbidden:
        raise ScoringConfigError(f"{field!r} must never be used as a scoring target for {decision_type!r}")
    return field


def score_one(result: dict, corpus_row_raw: dict, decision_type: str, target_field: str | None = None) -> ScoredPrediction:
    field = resolve_target_field(decision_type, target_field)
    ground_truth = corpus_row_raw.get(field)
    predicted = result.get("predicted_value")
    valid = bool(result.get("valid_prediction"))
    correct = (predicted == ground_truth) if (valid and ground_truth is not None) else None
    return ScoredPrediction(
        candidate_id=result["candidate_id"], predicted_value=predicted,
        valid_prediction=valid, ground_truth=ground_truth, correct=correct,
    )


def score_batch(
    results: list[dict], corpus_rows_by_id: dict[str, dict], decision_type: str,
    target_field: str | None = None,
) -> list[ScoredPrediction]:
    return [score_one(r, corpus_rows_by_id[r["candidate_id"]], decision_type, target_field) for r in results]


def summarize(scored: list[ScoredPrediction]) -> dict:
    """Decision/partition-agnostic numeric summary of one batch: accuracy, coverage,
    per-class counts, and a confusion matrix. Never combines batches -- callers (the
    aggregation stage) decide which rows belong in the same batch."""
    n = len(scored)
    valid = [s for s in scored if s.valid_prediction]
    correct = [s for s in valid if s.correct is True]
    incorrect = [s for s in valid if s.correct is False]

    # predicted_value only contributes a class when valid -- an off-contract garbage value
    # (e.g. "maybe") must never appear as its own confusion-matrix/per-class-count column.
    classes = sorted({
        v for s in scored
        for v in (s.ground_truth, s.predicted_value if s.valid_prediction else None)
        if v is not None
    })
    per_class_counts = {c: sum(1 for s in scored if s.ground_truth == c) for c in classes}
    confusion_matrix = {gt: {pred: 0 for pred in classes} for gt in classes}
    for s in valid:
        if s.ground_truth in confusion_matrix and s.predicted_value in confusion_matrix[s.ground_truth]:
            confusion_matrix[s.ground_truth][s.predicted_value] += 1

    return {
        "n": n,
        "valid_predictions": len(valid),
        "invalid_predictions": n - len(valid),
        "correct": len(correct),
        "incorrect": len(incorrect),
        "accuracy": (len(correct) / len(valid)) if valid else None,
        "coverage": (len(valid) / n) if n else None,
        "per_class_counts": per_class_counts,
        "confusion_matrix": confusion_matrix,
    }
