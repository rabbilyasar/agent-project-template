#!/usr/bin/env python3
"""Stage 5: model-agnostic confidence and calibration metrics.

Never fabricates confidence: when a canonical result's probability_distribution is
unavailable, calibration is reported as unavailable, not defaulted to 0 or an entropy-based
substitute. Decoupled from scoring/decision-type concerns -- operates only on
(confidence, correct) pairs that the scoring stage has already produced, so it works
identically for any decision_type or model_identifier.
"""
from __future__ import annotations


class CalibrationError(Exception):
    """Raised when a probability_distribution is present but malformed (doesn't sum to
    ~1, is missing the reported answer, or contains a negative mass) -- fails cleanly
    rather than silently computing a meaningless number."""


def answer_confidence(result: dict) -> float | None:
    """The probability mass a result's probability_distribution assigns to its own
    predicted_value. Returns None (never a fabricated value) when probability_distribution
    is unavailable. Deliberately not entropy-based -- entropy summarizes the whole
    distribution's spread, not confidence in the specific answer given."""
    dist = result.get("probability_distribution")
    if dist is None:
        return None
    predicted = result.get("predicted_value")
    if predicted is None or predicted not in dist:
        raise CalibrationError(
            f"{result.get('candidate_id')}: probability_distribution present but has no "
            f"mass entry for predicted_value {predicted!r}"
        )
    if any(p < 0 for p in dist.values()):
        raise CalibrationError(f"{result.get('candidate_id')}: probability_distribution has a negative probability")
    total = sum(dist.values())
    if not (0.99 <= total <= 1.01):
        raise CalibrationError(f"{result.get('candidate_id')}: probability_distribution sums to {total}, not 1")
    return dist[predicted]


def expected_calibration_error(confidence_correct_pairs: list[tuple[float, bool]], n_bins: int = 10) -> float | None:
    """Standard equal-width-binned ECE: bins answer_confidence into n_bins buckets in
    [0, 1], compares each bucket's mean confidence to its empirical accuracy, and weights
    by bucket size. Returns None (calibration unavailable) if given no pairs -- 0.0 would
    falsely claim perfect calibration."""
    if not confidence_correct_pairs:
        return None
    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for confidence, correct in confidence_correct_pairs:
        idx = min(int(confidence * n_bins), n_bins - 1)
        bins[idx].append((confidence, correct))
    total = len(confidence_correct_pairs)
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        bucket_confidence = sum(c for c, _ in bucket) / len(bucket)
        bucket_accuracy = sum(1 for _, correct in bucket if correct) / len(bucket)
        ece += (len(bucket) / total) * abs(bucket_confidence - bucket_accuracy)
    return ece


def calibration_summary(scored_with_confidence: list[tuple[float | None, bool | None]]) -> dict:
    """scored_with_confidence: (answer_confidence_or_None, correct_or_None) pairs, one per
    prediction. Predictions with no ground-truth-comparable outcome (correct is None, e.g.
    invalid predictions) are excluded -- calibration is about confidence vs. correctness,
    not about whether an answer was even valid."""
    pairs = [(c, correct) for c, correct in scored_with_confidence if c is not None and correct is not None]
    if not pairs:
        return {"available": False}
    return {
        "available": True,
        "n": len(pairs),
        "expected_calibration_error": expected_calibration_error(pairs),
    }
