#!/usr/bin/env python3
"""Self-tests for laya/harness/prompts/*.json -- the four vendor-neutral decision prompt
contracts. Verifies structure and, critically, that no contract's evaluator_supplies ever
names a candidate-identifying or ground-truth/provenance field."""
from __future__ import annotations

import json
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

REQUIRED_KEYS = {
    "decision_type", "decision_question", "allowed_output_values", "output_format",
    "evaluator_supplies", "forbidden_information", "ground_truth_target_field",
    "scored", "evaluation_notes",
}

MUST_BE_FORBIDDEN = {
    "candidate_id", "source_project", "source_artifact",
    "inclusion_status", "inclusion_reason", "clean_or_borderline", "confound_reason",
    "corpus_partition", "ambiguity_tier", "evidence_polarity", "evidence_source_type",
    "reused_evidence_of", "leakage_check", "eligible_for_binary_scoring",
}

EXPECTED_DECISION_TYPES = {
    "trivial_vs_staged", "agent_verification_applicable",
    "documented_limitation_vs_defect", "human_acceptance_required",
}

# The only value evaluator_supplies is allowed to name in this slice: the controlled
# model-facing projection itself. Nothing else may ever be listed as supplied.
ALLOWED_EVALUATOR_SUPPLIES = {"model_facing_input"}


def main() -> int:
    checks = []
    contracts = {}

    for name in EXPECTED_DECISION_TYPES:
        path = PROMPTS_DIR / f"{name}.json"
        checks.append((f"{name}.json exists", path.exists()))
        if not path.exists():
            continue
        contract = json.loads(path.read_text(encoding="utf-8"))
        contracts[name] = contract
        checks.append((f"{name}.json has all required keys", REQUIRED_KEYS <= set(contract)))
        checks.append((f"{name}.json decision_type matches filename", contract.get("decision_type") == name))
        checks.append((f"{name}.json allowed_output_values has exactly 2 values",
                       isinstance(contract.get("allowed_output_values"), list) and len(contract["allowed_output_values"]) == 2))
        checks.append((f"{name}.json evaluator_supplies names only model_facing_input",
                       set(contract.get("evaluator_supplies", [])) <= ALLOWED_EVALUATOR_SUPPLIES))
        forbidden = set(contract.get("forbidden_information", []))
        checks.append((f"{name}.json forbidden_information covers all provenance/metadata fields",
                       MUST_BE_FORBIDDEN <= forbidden))
        checks.append((f"{name}.json forbidden_information also lists candidate_id explicitly",
                       "candidate_id" in forbidden))

    if "trivial_vs_staged" in contracts:
        checks.append(("trivial_vs_staged is not scored", contracts["trivial_vs_staged"]["scored"] is False))
    for name in EXPECTED_DECISION_TYPES - {"trivial_vs_staged"}:
        if name in contracts:
            checks.append((f"{name} is scored", contracts[name]["scored"] is True))

    if "human_acceptance_required" in contracts:
        c = contracts["human_acceptance_required"]
        checks.append(("human_acceptance_required targets normative_label, not ground_truth_label",
                       c["ground_truth_target_field"] == "normative_label"))
        checks.append(("human_acceptance_required forbids empirical_label/empirical_basis",
                       {"empirical_label", "empirical_basis"} <= set(c["forbidden_information"])))
        checks.append(("human_acceptance_required allowed values are required/sufficient_without",
                       set(c["allowed_output_values"]) == {"required", "sufficient_without"}))

    for name in ["trivial_vs_staged", "agent_verification_applicable", "documented_limitation_vs_defect"]:
        if name in contracts:
            checks.append((f"{name} targets ground_truth_label",
                           contracts[name]["ground_truth_target_field"] == "ground_truth_label"))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  prompt contract checks failed: {failed}")
        return 1
    print(f"PASS  prompt contracts: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
