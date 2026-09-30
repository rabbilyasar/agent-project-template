"""Synthetic, in-memory-only fixtures for Slice 2 self-tests. These rows and results exist
only inside this test helper -- never added to the real Phase 4.1 corpus file."""
from __future__ import annotations

BASE_FIELDS = {
    "source_project": "synthetic", "source_artifact": "synthetic:1",
    "ground_truth_knowable_at": "before_implementation", "clean_or_borderline": "clean",
    "leakage_check": {"passed": True, "note": "synthetic"},
    "inclusion_status": "include", "inclusion_reason": "synthetic fixture",
    "ground_truth_evidence": {"quote": "q", "citation": "c", "verification_method": "m"},
}


def dp11_row(candidate_id: str, ground_truth: str) -> dict:
    return {
        **BASE_FIELDS, "candidate_id": candidate_id, "decision_type": "trivial_vs_staged",
        "decision_time_context": {"task_description": "synthetic task"},
        "model_facing_input": {"task_description": "synthetic task"},
        "ground_truth_label": ground_truth, "eligible_for_binary_scoring": False,
    }


def dp22_row(candidate_id: str, partition: str | None, ground_truth: str, files_touched: list[str] | None = None, ambiguity_tier: str = "obvious") -> dict:
    return {
        **BASE_FIELDS, "candidate_id": candidate_id, "decision_type": "agent_verification_applicable",
        "decision_time_context": {"files_touched": files_touched or [], "change_description": "synthetic"},
        "model_facing_input": {"files_touched": files_touched or [], "change_description": "synthetic"},
        "ground_truth_label": ground_truth, "ambiguity_tier": ambiguity_tier,
        "corpus_partition": partition, "eligible_for_binary_scoring": True,
    }


def dp16_row(candidate_id: str, polarity: str, ground_truth: str) -> dict:
    return {
        **BASE_FIELDS, "candidate_id": candidate_id, "decision_type": "documented_limitation_vs_defect",
        "decision_time_context": {"observed_behavior": "synthetic", "decision_doc_excerpt": "synthetic excerpt"},
        "model_facing_input": {"observed_behavior": "synthetic", "decision_doc_excerpt": "synthetic excerpt"},
        "ground_truth_label": ground_truth, "evidence_polarity": polarity, "eligible_for_binary_scoring": True,
    }


def dp23_row(candidate_id: str, normative_label: str, empirical_label: str = "substantive_engagement", relationship: str = "agree") -> dict:
    return {
        **BASE_FIELDS, "candidate_id": candidate_id, "decision_type": "human_acceptance_required",
        "decision_time_context": {"change_description": "synthetic"},
        "model_facing_input": {"change_description": "synthetic"},
        "ground_truth_label": None, "normative_label": normative_label, "normative_basis": "synthetic",
        "empirical_label": empirical_label, "empirical_basis": "synthetic",
        "normative_empirical_relationship": relationship, "eligible_for_binary_scoring": True,
    }


def canonical_result(
    candidate_id: str, decision_type: str, predicted_value: str | None, valid: bool = True,
    run_id: str = "test-run", corpus_hash: str = "0" * 64,
    probability_distribution: dict | None = None, confidence: float | None = None,
    latency_ms: float | None = None, input_tokens: int | None = None, output_tokens: int | None = None,
    error: str | None = None, model_identifier: str = "synthetic_model_v1",
    timestamp: str = "2026-01-01T00:00:00+00:00",
) -> dict:
    return {
        "candidate_id": candidate_id, "decision_type": decision_type, "run_id": run_id,
        "model_identifier": model_identifier, "predicted_value": predicted_value,
        "valid_prediction": valid, "confidence": confidence,
        "probability_distribution": probability_distribution,
        "latency_ms": latency_ms, "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cache_read_tokens": None, "cache_write_tokens": None, "error": error,
        "timestamp": timestamp, "corpus_content_hash": corpus_hash,
    }
