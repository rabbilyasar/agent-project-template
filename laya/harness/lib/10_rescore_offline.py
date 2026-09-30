#!/usr/bin/env python3
"""Stage 10: offline re-aggregation of a preserved run under the current scoring policy.

    preserved predictions.jsonl + current corpus -> existing aggregation (07) -> derived report

Zero model inference: imports no adapter, torch, laya, or network code -- it only reads an
existing run's predictions.jsonl and re-applies stage 7 (ADR-007 eligible-only scoring). The
source run directory is never written to (ADR-006); output goes to a sibling
<source_run_id>--rescore-eligible-only-v1/ directory with its own provenance manifest.

    python3 laya/harness/lib/10_rescore_offline.py laya/results/<run_id>
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent
REPO_DIR = LIB_DIR.parents[2]
sys.path.insert(0, str(LIB_DIR))
from _module_loader import load_lib_module  # noqa: E402

load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")
prefilter_mod = load_lib_module("04_deterministic_prefilter.py", "prefilter")
aggregate_mod = load_lib_module("07_aggregate_report.py", "aggregate")
serialize_mod = load_lib_module("08_serialize_result.py", "serialize")

SCORING_POLICY = "eligible_only_v1 (ADR-007)"
OUTPUT_SUFFIX = "--rescore-eligible-only-v1"
DP22_TYPE = "agent_verification_applicable"
SCORING_MODULES = ["05_calibration.py", "06_score.py", "07_aggregate_report.py", "10_rescore_offline.py"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_DIR), *args], capture_output=True, text=True, check=True).stdout.strip()


def build_reports(predictions: list[dict], corpus_rows_by_id: dict, corpus_hash: str, schema_version: str) -> dict:
    """Same per-decision-type composition as 09_run_evaluation*.py, generalized to any
    adapter: DP-22 gets one block set per model_identifier (prefilter vs. model, never
    merged); every other type must come from a single model_identifier."""
    run_id = predictions[0]["run_id"]
    by_type: dict[str, list[dict]] = {}
    for p in predictions:
        by_type.setdefault(p["decision_type"], []).append(p)

    reports: dict[str, dict] = {}
    for decision_type, results in by_type.items():
        if decision_type == DP22_TYPE:
            continue
        ids = {r["model_identifier"] for r in results}
        if len(ids) != 1:
            raise SystemExit(f"ABORT: {decision_type} mixes model_identifiers {sorted(ids)}")
        reports[decision_type] = aggregate_mod.build_report(
            decision_type, results, corpus_rows_by_id, run_id, corpus_hash, schema_version, ids.pop(),
        )

    blocks: dict[str, dict] = {}
    for mid in sorted({r["model_identifier"] for r in by_type.get(DP22_TYPE, [])}):
        subset = [r for r in by_type[DP22_TYPE] if r["model_identifier"] == mid]
        sub_blocks = aggregate_mod.build_report(
            DP22_TYPE, subset, corpus_rows_by_id, run_id, corpus_hash, schema_version, mid,
        )["blocks"]
        if set(sub_blocks) & set(blocks):
            raise SystemExit(f"ABORT: DP-22 partition produced by more than one model_identifier: {set(sub_blocks) & set(blocks)}")
        blocks.update(sub_blocks)
    if blocks:
        reports[DP22_TYPE] = {
            "run_id": run_id, "corpus_content_hash": corpus_hash, "schema_version": schema_version,
            "decision_type": DP22_TYPE, "model_identifier": "mixed (see per-block model_identifier)",
            "blocks": blocks,
        }
    return reports


def main(source_dir: str) -> None:
    source = Path(source_dir).resolve()
    predictions_path, source_manifest_path = source / "predictions.jsonl", source / "manifest.json"
    source_report_path = source / "aggregate_report.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    predictions = serialize_mod.read_results_jsonl(predictions_path)

    rows, corpus_hash = load_corpus_mod.load_corpus()
    if source_manifest["corpus_content_hash"] != corpus_hash or any(p["corpus_content_hash"] != corpus_hash for p in predictions):
        raise SystemExit("ABORT: preserved run was not produced against the current corpus hash")
    if {p["run_id"] for p in predictions} != {source_manifest["run_id"]}:
        raise SystemExit("ABORT: predictions.jsonl run_id does not match its manifest")
    corpus_rows_by_id = {r.candidate_id: r.raw for r in rows}
    if {p["candidate_id"] for p in predictions} != set(corpus_rows_by_id) or len(predictions) != len(corpus_rows_by_id):
        raise SystemExit("ABORT: predictions do not cover the corpus exactly once per row")

    source_hashes = {p.name: _sha256(p) for p in (predictions_path, source_manifest_path, source_report_path)}
    reports = build_reports(predictions, corpus_rows_by_id, corpus_hash, source_manifest["result_schema_version"])

    out_dir = source.parent / f"{source.name}{OUTPUT_SUFFIX}"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "aggregate_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    if {p.name: _sha256(p) for p in (predictions_path, source_manifest_path, source_report_path)} != source_hashes:
        raise SystemExit("ABORT: source run artifacts changed during re-aggregation")

    manifest = {
        "derived_artifact_id": out_dir.name,
        "derivation": "offline re-aggregation of preserved predictions; no model inference, no adapter, no network",
        "model_inference_performed": False,
        "scoring_policy": SCORING_POLICY,
        "source_run_id": source_manifest["run_id"],
        "source_run_dir": str(source.relative_to(REPO_DIR)),
        "source_artifact_sha256": source_hashes,
        "source_artifacts_modified": False,
        "corpus_content_hash": corpus_hash,
        "result_schema_version": source_manifest["result_schema_version"],
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "source_model_identifier": source_manifest.get("model_identifier"),
        "harness_git_commit": _git("rev-parse", "HEAD"),
        "harness_uncommitted_changes": bool(_git("status", "--porcelain", "--", "laya/harness", "laya/validate_corpus.py")),
        "scoring_module_sha256": {name: _sha256(LIB_DIR / name) for name in SCORING_MODULES},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote: {out_dir}/aggregate_report.json")
    print(f"Wrote: {out_dir}/manifest.json")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: 10_rescore_offline.py laya/results/<run_id>")
    main(sys.argv[1])
