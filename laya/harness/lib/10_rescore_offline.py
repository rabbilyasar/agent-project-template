#!/usr/bin/env python3
"""Stage 10: offline re-aggregation of a preserved run under the current scoring policy.

    preserved predictions.jsonl + current corpus -> existing aggregation (07) -> derived report

Zero model inference: imports no adapter, torch, laya, or network code, and reads no
credentials -- it only reads an existing run's predictions.jsonl and re-applies stage 7
(ADR-007 eligible-only scoring, ADR-008 DP-23 class coverage). The source run directory is
never written to (ADR-006); output goes to a sibling directory with its own provenance manifest.

Default (strict): the run must have been produced against the current corpus hash.

    python3 laya/harness/lib/10_rescore_offline.py laya/results/<run_id>

ADR-008 (explicit, narrow): a run produced against the original Phase 4.1 corpus may be
rescored against the corrected corpus only if the two corpora differ in exactly the one
approved field (AGENT-DP23-01 eligible_for_binary_scoring true -> false). The original corpus
is read from git at the pinned commit; both hashes must be stated on the command line.

    python3 laya/harness/lib/10_rescore_offline.py laya/results/<run_id> \
        --adr008-eligibility-correction <original_sha256> <corrected_sha256>
"""
from __future__ import annotations

import argparse
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

SCORING_POLICY = "eligible_only_v2 (ADR-007 eligibility, ADR-008 clean-include rows and DP-23 class coverage)"
OUTPUT_SUFFIX = "--rescore-eligible-only-v2"
CORRECTED_OUTPUT_SUFFIX = "--rescore-eligible-only-v2-corrected-corpus"
CORPUS_REL_PATH = "laya/corpus/phase-4.1-decision-corpus.jsonl"

# ADR-008: the single approved corpus correction a historical run may be rescored across.
# Not a general "ignore hash mismatch" switch: both hashes and the one field change are pinned.
ADR008_CORRECTION = {
    "adr": "ADR-008",
    "original_corpus_sha256": "a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b",
    "original_corpus_git_rev": "383390a2bf56096d673ac0cf0fa3cc64180664da",
    "corrected_corpus_sha256": "3e52a365c337f5bae70a20ce1ade19dd7153da35aed47d991eaa099fefd87e21",
    "candidate_id": "AGENT-DP23-01",
    "field": "eligible_for_binary_scoring",
    "from": True,
    "to": False,
}
DP22_TYPE = "agent_verification_applicable"
SCORING_MODULES = ["05_calibration.py", "06_score.py", "07_aggregate_report.py", "10_rescore_offline.py"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO_DIR), *args], capture_output=True, text=True, check=True).stdout.strip()


class CorpusDiffError(Exception):
    """The original and corrected corpora differ in anything other than the approved correction."""


def _parse_jsonl(data: bytes) -> list[dict]:
    return [json.loads(line) for line in data.decode("utf-8").splitlines() if line.strip()]


def verify_eligibility_only_correction(original: bytes, corrected: bytes, correction: dict) -> None:
    """Raises CorpusDiffError unless both corpora match their pinned hashes and differ in
    exactly one field of one row, as named by `correction`. Row identity, row order, field
    order and every other value (compared as serialized JSON, so true never equals 1) must
    be unchanged."""
    for label, data, key in (("original", original, "original_corpus_sha256"), ("corrected", corrected, "corrected_corpus_sha256")):
        actual = hashlib.sha256(data).hexdigest()
        if actual != correction[key]:
            raise CorpusDiffError(f"{label} corpus sha256 is {actual}, expected {correction[key]}")
    before, after = _parse_jsonl(original), _parse_jsonl(corrected)
    if [r.get("candidate_id") for r in before] != [r.get("candidate_id") for r in after]:
        raise CorpusDiffError("corpus row identities or ordering differ")
    diffs = []
    for a, b in zip(before, after):
        if list(a) != list(b):
            diffs.append((a["candidate_id"], "<field set or order>", json.dumps(list(a)), json.dumps(list(b))))
            continue
        diffs += [(a["candidate_id"], k, json.dumps(a[k]), json.dumps(b[k])) for k in a if json.dumps(a[k]) != json.dumps(b[k])]
    expected = [(correction["candidate_id"], correction["field"], json.dumps(correction["from"]), json.dumps(correction["to"]))]
    if diffs != expected:
        raise CorpusDiffError(f"corpus differences {diffs} are not exactly the approved correction {expected}")


def check_prediction_coverage(predictions: list[dict], corpus_rows_by_id: dict, skipped_excluded_ids: list[str]) -> None:
    """Every corpus row must be predicted exactly once, except rows the run's own manifest
    lists as skipped, and only if each of those is inclusion_status=exclude (Phase 4.6)."""
    ids = [p["candidate_id"] for p in predictions]
    if len(ids) != len(set(ids)) or set(ids) - set(corpus_rows_by_id):
        raise SystemExit("ABORT: predictions contain duplicate or unknown candidate_ids")
    missing = set(corpus_rows_by_id) - set(ids)
    if missing != set(skipped_excluded_ids) or any(corpus_rows_by_id[c].get("inclusion_status") != "exclude" for c in missing):
        raise SystemExit(f"ABORT: predictions do not cover the corpus; missing {sorted(missing)}, "
                         f"manifest-listed excluded skips {sorted(skipped_excluded_ids)}")


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


def main(source_dir: str, correction_hashes: list[str] | None = None) -> None:
    source = Path(source_dir).resolve()
    predictions_path, source_manifest_path = source / "predictions.jsonl", source / "manifest.json"
    source_report_path = source / "aggregate_report.json"
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    predictions = serialize_mod.read_results_jsonl(predictions_path)

    rows, corpus_hash = load_corpus_mod.load_corpus()
    prediction_corpus_hash = corpus_hash
    correction = None
    if correction_hashes is not None:
        correction = ADR008_CORRECTION
        if correction_hashes != [correction["original_corpus_sha256"], correction["corrected_corpus_sha256"]]:
            raise SystemExit(f"ABORT: stated hashes {correction_hashes} are not the ADR-008 pinned hashes "
                             f"{[correction['original_corpus_sha256'], correction['corrected_corpus_sha256']]}")
        original = subprocess.run(
            ["git", "-C", str(REPO_DIR), "show", f"{correction['original_corpus_git_rev']}:{CORPUS_REL_PATH}"],
            capture_output=True, check=True,
        ).stdout
        try:
            verify_eligibility_only_correction(original, load_corpus_mod.CORPUS_PATH.read_bytes(), correction)
        except CorpusDiffError as exc:
            raise SystemExit(f"ABORT: {exc}") from exc
        if corpus_hash != correction["corrected_corpus_sha256"]:
            raise SystemExit("ABORT: loaded corpus is not the ADR-008 corrected corpus")
        prediction_corpus_hash = correction["original_corpus_sha256"]
    if source_manifest["corpus_content_hash"] != prediction_corpus_hash or any(
        p["corpus_content_hash"] != prediction_corpus_hash for p in predictions
    ):
        raise SystemExit(f"ABORT: preserved run was not produced against corpus hash {prediction_corpus_hash}")
    if {p["run_id"] for p in predictions} != {source_manifest["run_id"]}:
        raise SystemExit("ABORT: predictions.jsonl run_id does not match its manifest")
    corpus_rows_by_id = {r.candidate_id: r.raw for r in rows}
    skipped = source_manifest.get("skipped_excluded_candidate_ids", [])
    check_prediction_coverage(predictions, corpus_rows_by_id, skipped)

    source_hashes = {p.name: _sha256(p) for p in (predictions_path, source_manifest_path, source_report_path)}
    reports = build_reports(predictions, corpus_rows_by_id, corpus_hash, source_manifest["result_schema_version"])

    out_dir = source.parent / f"{source.name}{CORRECTED_OUTPUT_SUFFIX if correction else OUTPUT_SUFFIX}"
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
        "prediction_corpus_content_hash": prediction_corpus_hash,
        "scoring_corpus_content_hash": corpus_hash,
        "corpus_correction": None if correction is None else {
            **correction,
            "original_corpus_source": f"git show {correction['original_corpus_git_rev']}:{CORPUS_REL_PATH}",
            "verified": "corpora differ only in this one field of this one row",
        },
        "skipped_excluded_candidate_ids": skipped,
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
    parser = argparse.ArgumentParser(description="Offline re-aggregation of a preserved run (no model inference).")
    parser.add_argument("run_dir", help="laya/results/<run_id>")
    parser.add_argument("--adr008-eligibility-correction", nargs=2, metavar=("ORIGINAL_SHA256", "CORRECTED_SHA256"),
                        help="rescore a run made against the original corpus, across the single ADR-008 correction")
    args = parser.parse_args()
    main(args.run_dir, args.adr008_eligibility_correction)
