#!/usr/bin/env python3
"""Stage 1: read-only corpus loader for Phase 4.2 evaluation.

Loads laya/corpus/phase-4.1-decision-corpus.jsonl, validates it against the existing
corpus schema/validator (laya/validate_corpus.py -- not reimplemented here), and exposes
only what an evaluation run needs: a typed, read-only view per row plus the corpus's
content hash and declared schema_version.

Never mutates or writes to corpus/. Never invokes any model. Invalid rows, duplicate
IDs, or an unsupported decision_type raise CorpusLoadError -- this loader does not
silently repair or skip malformed data.
"""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

_LAYA_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_LAYA_DIR))
import validate_corpus as _vc  # noqa: E402

CORPUS_PATH = _LAYA_DIR / "corpus" / "phase-4.1-decision-corpus.jsonl"
SCHEMA_PATH = _LAYA_DIR / "schema" / "decision_corpus_schema.json"
EXPECTED_SCHEMA_VERSION = "1.0"

VALID_DECISION_TYPES = _vc.VALID_DECISION_TYPES


class CorpusLoadError(Exception):
    """Raised when the corpus fails validation. The evaluation harness must not proceed
    past a CorpusLoadError -- there is no partial/best-effort load mode."""


@dataclass(frozen=True)
class CorpusRow:
    candidate_id: str
    decision_type: str
    model_facing_input: object
    raw: dict
    """`raw` is the full corpus row, including all ground-truth/evidence/partition/
    provenance fields. It exists for harness-internal use only (scoring a prediction
    against ground truth after the fact) and must never be used to construct a model
    prompt -- use model_facing_payload()/model_facing_input for that."""


def compute_corpus_hash(path: Path = CORPUS_PATH) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_schema_version(path: Path = SCHEMA_PATH) -> str | None:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("schema_version")


def load_corpus(path: Path = CORPUS_PATH, schema_path: Path = SCHEMA_PATH) -> tuple[list[CorpusRow], str]:
    """Returns (rows, corpus_content_hash). Raises CorpusLoadError on any validation
    failure -- schema_version mismatch, schema-field errors, leakage-check failures, ID
    duplicates, or an unsupported decision_type."""
    version = load_schema_version(schema_path)
    if version != EXPECTED_SCHEMA_VERSION:
        raise CorpusLoadError(f"corpus schema_version={version!r}, expected {EXPECTED_SCHEMA_VERSION!r}")

    try:
        raw_rows = _vc.load_rows()
    except SystemExit as e:
        raise CorpusLoadError(str(e)) from e

    hard_checks = [
        _vc.check_schema_fields(raw_rows),
        _vc.check_model_input_derivable(raw_rows),
        _vc.check_leakage_excluded(raw_rows),
        _vc.check_unique_ids(raw_rows),
        _vc.check_inclusion_status_consistency(raw_rows),
        _vc.check_dp23_fields(raw_rows),
        _vc.check_dp11_no_clean_trivial(raw_rows),
        _vc.check_dp16_polarity(raw_rows),
        _vc.check_dp22_partitions(raw_rows),
    ]
    all_errors = [e for errs in hard_checks for e in errs]
    if all_errors:
        raise CorpusLoadError(f"{len(all_errors)} corpus validation error(s): {all_errors}")

    rows = []
    for r in raw_rows:
        if r["decision_type"] not in VALID_DECISION_TYPES:
            raise CorpusLoadError(f"{r.get('candidate_id')}: unsupported decision_type {r.get('decision_type')!r}")
        rows.append(CorpusRow(
            candidate_id=r["candidate_id"],
            decision_type=r["decision_type"],
            model_facing_input=r["model_facing_input"],
            raw=r,
        ))

    return rows, compute_corpus_hash(path)


def model_facing_payload(row: CorpusRow):
    """The ONLY content ever eligible for prompt construction. Never returns candidate_id,
    source_project/source_artifact, or any ground-truth/evidence/partition/provenance field."""
    return row.model_facing_input


def main() -> int:
    try:
        rows, corpus_hash = load_corpus()
    except CorpusLoadError as e:
        print(f"FAIL  corpus load: {e}")
        return 1
    print(f"PASS  loaded {len(rows)} rows, corpus_content_hash={corpus_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
