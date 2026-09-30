#!/usr/bin/env python3
"""Self-tests for lib/05_calibration.py, against synthetic fixtures only."""
from __future__ import annotations

from _fixtures import canonical_result
from _load_lib import load_lib_module

calibration = load_lib_module("05_calibration.py", "calibration")


def main() -> int:
    checks = []

    with_dist = canonical_result(
        "A", "agent_verification_applicable", "applicable",
        probability_distribution={"applicable": 0.8, "not_applicable": 0.2},
    )
    conf = calibration.answer_confidence(with_dist)
    checks.append(("valid probability distribution produces answer_confidence", conf == 0.8))

    no_dist = canonical_result("B", "agent_verification_applicable", "applicable")
    checks.append(("missing probability_distribution -> None, not 0.0", calibration.answer_confidence(no_dist) is None))

    malformed = canonical_result(
        "C", "agent_verification_applicable", "applicable",
        probability_distribution={"applicable": 0.3, "not_applicable": 0.3},
    )
    try:
        calibration.answer_confidence(malformed)
        checks.append(("distribution not summing to 1 fails cleanly", False))
    except calibration.CalibrationError:
        checks.append(("distribution not summing to 1 fails cleanly", True))

    missing_answer_mass = canonical_result(
        "D", "agent_verification_applicable", "applicable",
        probability_distribution={"not_applicable": 1.0},
    )
    try:
        calibration.answer_confidence(missing_answer_mass)
        checks.append(("distribution missing the predicted_value's own mass fails cleanly", False))
    except calibration.CalibrationError:
        checks.append(("distribution missing the predicted_value's own mass fails cleanly", True))

    negative_mass = canonical_result(
        "E", "agent_verification_applicable", "applicable",
        probability_distribution={"applicable": 1.2, "not_applicable": -0.2},
    )
    try:
        calibration.answer_confidence(negative_mass)
        checks.append(("negative probability mass fails cleanly", False))
    except calibration.CalibrationError:
        checks.append(("negative probability mass fails cleanly", True))

    # Deterministic ECE: two perfectly-calibrated buckets (both bins where confidence == accuracy).
    pairs = [(0.9, True), (0.9, True), (0.9, False), (0.1, False), (0.1, False), (0.1, True)]
    # bucket 0.9 (idx 9): accuracy = 2/3 = 0.667, |0.9-0.667| = 0.233, weight 3/6
    # bucket 0.1 (idx 1): accuracy = 1/3 = 0.333, |0.1-0.333| = 0.233, weight 3/6
    expected_ece = 0.5 * abs(0.9 - (2 / 3)) + 0.5 * abs(0.1 - (1 / 3))
    ece = calibration.expected_calibration_error(pairs)
    checks.append(("ECE calculation has a deterministic expected result", abs(ece - expected_ece) < 1e-9))

    checks.append(("ECE of a perfectly calibrated set is ~0", abs(calibration.expected_calibration_error([(1.0, True), (1.0, True)])) < 1e-9))
    checks.append(("ECE with no pairs is unavailable (None), not 0.0", calibration.expected_calibration_error([]) is None))

    checks.append(("calibration_summary with no usable pairs reports unavailable", calibration.calibration_summary([(None, True), (0.5, None)]) == {"available": False}))
    summary = calibration.calibration_summary([(0.9, True), (0.1, False)])
    checks.append(("calibration_summary with usable pairs reports available + n + ECE", summary["available"] is True and summary["n"] == 2 and "expected_calibration_error" in summary))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  calibration checks failed: {failed}")
        return 1
    print(f"PASS  calibration: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
