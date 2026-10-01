#!/usr/bin/env python3
"""Self-tests for lib/01_load_corpus.py. Runs against the real corpus for the positive
path (never mutating it) and synthetic, in-memory-only fixtures for negative paths.
Never adds a synthetic row to the actual corpus file."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _load_lib import load_lib_module

load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")

REAL_CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "phase-4.1-decision-corpus.jsonl"
REAL_SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "decision_corpus_schema.json"

MINIMAL_ROW = {
    "candidate_id": "SYN-01", "decision_type": "trivial_vs_staged",
    "source_project": "synthetic", "source_artifact": "synthetic:1",
    "decision_time_context": {"task_description": "rename a variable"},
    "model_facing_input": {"task_description": "rename a variable"},
    "ground_truth_label": "trivial", "ground_truth_knowable_at": "before_implementation",
    "clean_or_borderline": "clean", "leakage_check": {"passed": True, "note": "synthetic"},
    "inclusion_status": "include", "inclusion_reason": "synthetic fixture",
    "eligible_for_binary_scoring": False,
    "ground_truth_evidence": {"quote": "q", "citation": "c", "verification_method": "m"},
}


def _write_jsonl(rows, tmp_dir: Path) -> Path:
    path = tmp_dir / "corpus.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


def _write_schema(tmp_dir: Path, version: str) -> Path:
    path = tmp_dir / f"schema-{version}.json"
    path.write_text(json.dumps({"schema_version": version}), encoding="utf-8")
    return path


def main() -> int:
    checks = []

    # --- positive path: the real corpus ---
    before_bytes = REAL_CORPUS.read_bytes()
    rows, corpus_hash = load_corpus_mod.load_corpus()
    after_bytes = REAL_CORPUS.read_bytes()
    checks.append(("loads all 36 real rows", len(rows) == 36))
    checks.append(("loader never mutates the corpus file on disk", before_bytes == after_bytes))
    checks.append(("corpus_content_hash is a 64-char hex sha256", len(corpus_hash) == 64 and all(c in "0123456789abcdef" for c in corpus_hash)))
    rows2, corpus_hash2 = load_corpus_mod.load_corpus()
    checks.append(("corpus_content_hash is deterministic across repeated loads", corpus_hash == corpus_hash2))

    counts = {}
    for r in rows:
        counts[r.decision_type] = counts.get(r.decision_type, 0) + 1
    checks.append(("decision_type counts are exactly 7/9/8/12", counts == {
        "trivial_vs_staged": 7, "agent_verification_applicable": 9,
        "documented_limitation_vs_defect": 8, "human_acceptance_required": 12,
    }))

    sample = next(r for r in rows if r.candidate_id == "ENV-DP11-01")
    payload = load_corpus_mod.model_facing_payload(sample)
    checks.append(("model_facing_payload returns exactly model_facing_input", payload == sample.model_facing_input))
    checks.append(("model_facing_payload never exposes candidate_id",
                   "candidate_id" not in (payload if isinstance(payload, dict) else {})))
    checks.append(("CorpusRow.raw retains full row for harness-internal scoring use",
                   sample.raw.get("candidate_id") == "ENV-DP11-01"))

    try:
        sample.candidate_id = "mutated"
        checks.append(("CorpusRow is frozen/read-only", False))
    except Exception:
        checks.append(("CorpusRow is frozen/read-only", True))

    # --- negative paths: synthetic fixtures only, never touching the real corpus ---
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)

        good_schema = _write_schema(tmp_dir, "1.0")
        bad_schema = _write_schema(tmp_dir, "0.9")
        good_corpus = _write_jsonl([MINIMAL_ROW], tmp_dir)

        try:
            load_corpus_mod.load_corpus(path=good_corpus, schema_path=bad_schema)
            checks.append(("schema_version mismatch raises CorpusLoadError", False))
        except load_corpus_mod.CorpusLoadError:
            checks.append(("schema_version mismatch raises CorpusLoadError", True))

        dup_corpus = _write_jsonl([MINIMAL_ROW, MINIMAL_ROW], tmp_dir)
        try:
            load_corpus_mod.load_corpus(path=dup_corpus, schema_path=good_schema)
            checks.append(("duplicate candidate_id raises CorpusLoadError", False))
        except load_corpus_mod.CorpusLoadError:
            checks.append(("duplicate candidate_id raises CorpusLoadError", True))

        bad_type_row = dict(MINIMAL_ROW, candidate_id="SYN-02", decision_type="not_a_real_type")
        bad_type_corpus = _write_jsonl([bad_type_row], tmp_dir)
        try:
            load_corpus_mod.load_corpus(path=bad_type_corpus, schema_path=good_schema)
            checks.append(("unsupported decision_type raises CorpusLoadError", False))
        except load_corpus_mod.CorpusLoadError:
            checks.append(("unsupported decision_type raises CorpusLoadError", True))

        missing_field_row = {k: v for k, v in MINIMAL_ROW.items() if k != "ground_truth_evidence"}
        missing_field_row["candidate_id"] = "SYN-03"
        missing_corpus = _write_jsonl([missing_field_row], tmp_dir)
        try:
            load_corpus_mod.load_corpus(path=missing_corpus, schema_path=good_schema)
            checks.append(("row missing a required field raises CorpusLoadError", False))
        except load_corpus_mod.CorpusLoadError:
            checks.append(("row missing a required field raises CorpusLoadError", True))

        leaky_row = dict(MINIMAL_ROW)
        leaky_row["candidate_id"] = "SYN-04"
        leaky_row["normative_basis"] = "this is a sufficiently long normative basis string for the exact-copy check"
        leaky_row["model_facing_input"] = {
            "task_description": "this is a sufficiently long normative basis string for the exact-copy check"
        }
        leaky_row["decision_time_context"] = dict(leaky_row["model_facing_input"])
        leaky_corpus = _write_jsonl([leaky_row], tmp_dir)
        try:
            load_corpus_mod.load_corpus(path=leaky_corpus, schema_path=good_schema)
            checks.append(("post-decision evidence copied into model_facing_input raises CorpusLoadError", False))
        except load_corpus_mod.CorpusLoadError:
            checks.append(("post-decision evidence copied into model_facing_input raises CorpusLoadError", True))

        # --- ADR-008: only clean, include rows may be eligible_for_binary_scoring ---
        scorable_row = dict(
            MINIMAL_ROW, candidate_id="SYN-05", decision_type="documented_limitation_vs_defect",
            ground_truth_label="deliberate", evidence_polarity="positive_match", eligible_for_binary_scoring=True,
        )
        eligibility_cases = [
            ("clean, include, eligible row loads", {}, True),
            ("borderline, include, eligible row raises CorpusLoadError", {"clean_or_borderline": "borderline"}, False),
            ("clean, exclude, eligible row raises CorpusLoadError", {"inclusion_status": "exclude"}, False),
            ("borderline, include, ineligible row loads",
             {"clean_or_borderline": "borderline", "eligible_for_binary_scoring": False}, True),
        ]
        for name, overrides, should_load in eligibility_cases:
            corpus = _write_jsonl([dict(scorable_row, **overrides)], tmp_dir)
            try:
                load_corpus_mod.load_corpus(path=corpus, schema_path=good_schema)
                checks.append((name, should_load))
            except load_corpus_mod.CorpusLoadError as exc:
                checks.append((name, not should_load and "only clean, include rows may be eligible" in str(exc)))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  corpus loader checks failed: {failed}")
        return 1
    print(f"PASS  corpus loader: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
