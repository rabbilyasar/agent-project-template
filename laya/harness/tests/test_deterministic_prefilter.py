#!/usr/bin/env python3
"""Self-tests for lib/04_deterministic_prefilter.py, against synthetic fixtures only."""
from __future__ import annotations

from _load_lib import load_lib_module

prefilter = load_lib_module("04_deterministic_prefilter.py", "prefilter")


def main() -> int:
    checks = []

    frontend = prefilter.deterministic_prefilter(
        "agent_verification_applicable", {"files_touched": ["src/app/components/Widget.tsx"]}
    )
    checks.append(("known frontend-looking path -> applicable", frontend == {
        "handled": True, "predicted_value": "applicable",
        "reason": "path matches a known frontend file extension or directory keyword",
        "rule_version": "1.0",
    }))

    backend = prefilter.deterministic_prefilter(
        "agent_verification_applicable", {"files_touched": ["src/app/repository/user_repository.py"]}
    )
    checks.append(("backend-only path with no known frontend consumer -> not_applicable", backend == {
        "handled": True, "predicted_value": "not_applicable",
        "reason": "path matches a known backend-only keyword with no frontend marker present",
        "rule_version": "1.0",
    }))

    ambiguous = prefilter.deterministic_prefilter(
        "agent_verification_applicable", {"files_touched": ["athena/travel/tour/views/details.py"]}
    )
    checks.append(("ambiguous path -> defer (handled=False, predicted_value=None)",
                   ambiguous["handled"] is False and ambiguous["predicted_value"] is None))

    non_dp22 = prefilter.deterministic_prefilter("trivial_vs_staged", {"task_description": "anything"})
    checks.append(("non-DP-22 decision_type -> defer unconditionally",
                   non_dp22["handled"] is False and non_dp22["predicted_value"] is None))

    for out in (frontend, backend, ambiguous, non_dp22):
        checks.append((f"rule_version present in {out['reason'][:20]}...", out.get("rule_version") == "1.0"))

    # Ground truth is not an accepted parameter at all -- deterministic_prefilter()'s only
    # inputs are decision_type and model_facing_input.
    import inspect
    sig = inspect.signature(prefilter.deterministic_prefilter)
    checks.append(("deterministic_prefilter() takes no ground-truth parameter",
                   set(sig.parameters) == {"decision_type", "model_facing_input"}))

    valid_result = prefilter.build_canonical_result(
        "SYN-01", "agent_verification_applicable", "run-1", "deadbeef" * 8,
        ["applicable", "not_applicable"], frontend,
    )
    checks.append(("build_canonical_result marks a handled prediction valid", valid_result["valid_prediction"] is True))
    checks.append(("build_canonical_result carries the corpus_content_hash through", valid_result["corpus_content_hash"] == "deadbeef" * 8))
    checks.append(("build_canonical_result leaves token fields null, not zero", valid_result["input_tokens"] is None and valid_result["output_tokens"] is None))
    checks.append(("build_canonical_result does not fabricate confidence", valid_result["confidence"] is None and valid_result["probability_distribution"] is None))

    deferred_result = prefilter.build_canonical_result(
        "SYN-02", "agent_verification_applicable", "run-1", "deadbeef" * 8,
        ["applicable", "not_applicable"], ambiguous,
    )
    checks.append(("a deferred case still produces a canonical result", deferred_result["predicted_value"] is None))
    checks.append(("a deferred case is not a valid_prediction", deferred_result["valid_prediction"] is False))

    try:
        prefilter.build_canonical_result(
            "SYN-03", "agent_verification_applicable", "run-1", "deadbeef" * 8,
            ["applicable", "not_applicable"], {"handled": True, "predicted_value": "maybe", "reason": "bad", "rule_version": "1.0"},
        )
        checks.append(("an off-contract prediction is never coerced into valid", False))
    except ValueError:
        checks.append(("an off-contract prediction is never coerced into valid", True))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  deterministic prefilter checks failed: {failed}")
        return 1
    print(f"PASS  deterministic prefilter: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
