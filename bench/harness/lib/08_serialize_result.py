#!/usr/bin/env python3
"""Stage 8: result serialization.

Combines run metadata with the outputs of stages 5-7 into one JSON line
matching schema/result_schema.json, and appends it to the given output file.
Deliberately carries no pricing/dollar field -- see
schema/pricing.example.json for how cost is computed separately, later, from
the raw token counts recorded here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED_FIELDS = (
    "task_id",
    "arm",
    "trial_id",
    "fixture_commit",
    "template_commit",
    "model_id",
    "claude_code_version",
    "timestamp",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "tool_calls",
    "files_read",
    "files_modified",
    "wall_time",
    "validation_result",
    "safety_result",
    "human_intervention_count",
)


def serialize(record: dict) -> str:
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    if missing:
        raise ValueError(f"result record missing required fields: {missing}")
    return json.dumps({field: record[field] for field in REQUIRED_FIELDS})


def append(record: dict, output_path: Path) -> None:
    line = serialize(record)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"Usage: {argv[0]} <record.json> <output.jsonl>", file=sys.stderr)
        return 2

    with open(argv[1], encoding="utf-8") as fh:
        record = json.load(fh)

    append(record, Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
