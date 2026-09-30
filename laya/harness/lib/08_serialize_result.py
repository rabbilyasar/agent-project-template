#!/usr/bin/env python3
"""Stage 8: deterministic serialization.

Validates a canonical result against laya/schema/result_schema.json and writes/reads
JSON/JSONL. Serialization is reproducible except for explicitly time-varying fields
(timestamp, run_id) -- given the same result dict, serialize_result() always produces the
same bytes (json.dumps with sort_keys=True). raw_response is passed through opaquely and is
never inspected here or by anything upstream of scoring.

Refuses to write into laya/corpus/ -- evaluation output is not corpus data.
"""
from __future__ import annotations

import json
from pathlib import Path

RESULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "result_schema.json"
CORPUS_DIR = Path(__file__).resolve().parents[2] / "corpus"


class ResultValidationError(Exception):
    """Raised when a result does not conform to result_schema.json's required fields."""


def _load_required_fields() -> list[str]:
    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    return schema["required"]


def validate_against_result_schema(result: dict) -> list[str]:
    required = _load_required_fields()
    errors = [f"missing required field {f!r}" for f in required if f not in result]
    return errors


def serialize_result(result: dict) -> str:
    errors = validate_against_result_schema(result)
    if errors:
        raise ResultValidationError(f"result does not conform to result_schema.json: {errors}")
    return json.dumps(result, sort_keys=True)


def deserialize_result(line: str) -> dict:
    return json.loads(line)


def _refuse_corpus_path(path: Path) -> None:
    resolved = path.resolve()
    if resolved == CORPUS_DIR or CORPUS_DIR in resolved.parents:
        raise ValueError(f"refusing to write evaluation results into laya/corpus/: {path}")


def write_results_jsonl(results: list[dict], path: Path) -> None:
    path = Path(path)
    _refuse_corpus_path(path)
    with open(path, "w", encoding="utf-8") as fh:
        for result in results:
            fh.write(serialize_result(result) + "\n")


def read_results_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(deserialize_result(line))
    return rows
