#!/usr/bin/env python3
"""Stage 7: aggregation.

Combines stage 6 (scoring) and stage 5 (calibration) into one machine-readable report per
decision_type, applying the decision-specific composition rules approved for Phase 4.2:

- trivial_vs_staged: never scored for accuracy (not_scored=true, reason given).
- agent_verification_applicable: exactly two separate blocks (deterministic_prefilter_
  validation, system1_judgment) -- NEVER combined into one metric or "overall" figure.
- documented_limitation_vs_defect: overall + positive_match + absence_based, kept separate.
- human_acceptance_required: one block, scored only against normative_label (enforced by
  stage 6's resolve_target_field, which raises on any other target).

Never produces model comparison, ranking, or "winner" language -- that is out of scope for
this slice and is not implemented here at all.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _module_loader import load_lib_module  # noqa: E402

_score = load_lib_module("06_score.py", "score")
_calibration = load_lib_module("05_calibration.py", "calibration")


def _numeric_stats(values: list) -> dict:
    vals = [v for v in values if v is not None]
    if not vals:
        return {"available": False}
    return {"available": True, "n": len(vals), "mean": sum(vals) / len(vals), "min": min(vals), "max": max(vals)}


def _calibration_for_batch(results_by_id: dict, scored: list) -> dict:
    pairs = []
    for s in scored:
        conf = _calibration.answer_confidence(results_by_id[s.candidate_id])
        pairs.append((conf, s.correct))
    return _calibration.calibration_summary(pairs)


def _block(
    decision_type: str, results: list[dict], corpus_rows_by_id: dict, run_id: str,
    corpus_content_hash: str, schema_version: str, model_identifier: str,
    partition: str | None = None, target_field: str | None = None,
) -> dict:
    scored = _score.score_batch(results, corpus_rows_by_id, decision_type, target_field)
    results_by_id = {r["candidate_id"]: r for r in results}
    block = {
        "run_id": run_id,
        "corpus_content_hash": corpus_content_hash,
        "schema_version": schema_version,
        "decision_type": decision_type,
        "model_identifier": model_identifier,
        **_score.summarize(scored),
        "latency_ms": _numeric_stats([r.get("latency_ms") for r in results]),
        "input_tokens": _numeric_stats([r.get("input_tokens") for r in results]),
        "output_tokens": _numeric_stats([r.get("output_tokens") for r in results]),
        "calibration": _calibration_for_batch(results_by_id, scored),
    }
    if partition is not None:
        block["partition"] = partition
    return block


def build_trivial_vs_staged_report(
    results: list[dict], run_id: str, corpus_content_hash: str, schema_version: str, model_identifier: str,
) -> dict:
    n = len(results)
    valid = [r for r in results if r.get("valid_prediction")]
    return {
        "run_id": run_id, "corpus_content_hash": corpus_content_hash, "schema_version": schema_version,
        "decision_type": "trivial_vs_staged", "model_identifier": model_identifier,
        "n": n, "valid_predictions": len(valid), "invalid_predictions": n - len(valid),
        "coverage": (len(valid) / n) if n else None,
        "accuracy": None,
        "not_scored": True,
        "reason": (
            "trivial_vs_staged has no clean real 'trivial' example and no row of this "
            "decision_type is eligible_for_binary_scoring; predictions are recorded for "
            "qualitative review only and must never be aggregated into an accuracy figure"
        ),
    }


def build_agent_verification_applicable_report(
    results: list[dict], corpus_rows_by_id: dict, run_id: str, corpus_content_hash: str,
    schema_version: str, model_identifier: str,
) -> dict:
    by_partition: dict[str, list[dict]] = {"deterministic_prefilter_validation": [], "system1_judgment": []}
    for r in results:
        partition = corpus_rows_by_id[r["candidate_id"]].get("corpus_partition")
        if partition in by_partition:
            by_partition[partition].append(r)

    blocks = {}
    for partition, group in by_partition.items():
        if not group:
            continue
        block = _block(
            "agent_verification_applicable", group, corpus_rows_by_id, run_id,
            corpus_content_hash, schema_version, model_identifier, partition=partition,
        )
        if partition == "system1_judgment":
            # Hardcoded, not a computed small-n rule: this partition's real corpus size is
            # fixed at exactly 2 rows (see laya/README.md) -- Phase 4.2 explicitly rejected
            # baking a generic n-threshold into the evaluator.
            block["sample_size_warning"] = True
        blocks[partition] = block

    return {
        "run_id": run_id, "corpus_content_hash": corpus_content_hash, "schema_version": schema_version,
        "decision_type": "agent_verification_applicable", "model_identifier": model_identifier,
        "blocks": blocks,
        # No "overall"/combined key: the two partitions must never be merged into one metric.
    }


def build_documented_limitation_vs_defect_report(
    results: list[dict], corpus_rows_by_id: dict, run_id: str, corpus_content_hash: str,
    schema_version: str, model_identifier: str,
) -> dict:
    by_polarity: dict[str, list[dict]] = {"positive_match": [], "absence_based": []}
    for r in results:
        polarity = corpus_rows_by_id[r["candidate_id"]].get("evidence_polarity")
        if polarity in by_polarity:
            by_polarity[polarity].append(r)

    blocks = {
        "overall": _block(
            "documented_limitation_vs_defect", results, corpus_rows_by_id, run_id,
            corpus_content_hash, schema_version, model_identifier,
        )
    }
    for polarity, group in by_polarity.items():
        if group:
            blocks[polarity] = _block(
                "documented_limitation_vs_defect", group, corpus_rows_by_id, run_id,
                corpus_content_hash, schema_version, model_identifier, partition=polarity,
            )

    return {
        "run_id": run_id, "corpus_content_hash": corpus_content_hash, "schema_version": schema_version,
        "decision_type": "documented_limitation_vs_defect", "model_identifier": model_identifier,
        "blocks": blocks,
    }


def build_human_acceptance_required_report(
    results: list[dict], corpus_rows_by_id: dict, run_id: str, corpus_content_hash: str,
    schema_version: str, model_identifier: str,
) -> dict:
    return _block(
        "human_acceptance_required", results, corpus_rows_by_id, run_id, corpus_content_hash,
        schema_version, model_identifier, target_field="normative_label",
    )


_BUILDERS = {
    "agent_verification_applicable": build_agent_verification_applicable_report,
    "documented_limitation_vs_defect": build_documented_limitation_vs_defect_report,
}


def build_report(
    decision_type: str, results: list[dict], corpus_rows_by_id: dict, run_id: str,
    corpus_content_hash: str, schema_version: str, model_identifier: str,
) -> dict:
    if decision_type == "trivial_vs_staged":
        return build_trivial_vs_staged_report(results, run_id, corpus_content_hash, schema_version, model_identifier)
    if decision_type == "human_acceptance_required":
        return build_human_acceptance_required_report(
            results, corpus_rows_by_id, run_id, corpus_content_hash, schema_version, model_identifier
        )
    builder = _BUILDERS.get(decision_type)
    if builder is None:
        raise ValueError(f"unsupported decision_type {decision_type!r}")
    return builder(results, corpus_rows_by_id, run_id, corpus_content_hash, schema_version, model_identifier)
