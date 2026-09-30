#!/usr/bin/env python3
"""Self-tests for lib/08_serialize_result.py, against synthetic fixtures only."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from _fixtures import canonical_result
from _load_lib import load_lib_module

serialize = load_lib_module("08_serialize_result.py", "serialize")

RESULT_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema" / "result_schema.json"


def main() -> int:
    checks = []

    result = canonical_result(
        "A", "agent_verification_applicable", "applicable",
        probability_distribution={"applicable": 0.9, "not_applicable": 0.1},
        latency_ms=12.5,
    )

    schema = json.loads(RESULT_SCHEMA_PATH.read_text(encoding="utf-8"))
    missing = [f for f in schema["required"] if f not in result]
    checks.append(("canonical result fixture validates against result_schema.json's required fields", not missing))
    checks.append(("validate_against_result_schema agrees the fixture is valid", serialize.validate_against_result_schema(result) == []))

    incomplete = dict(result)
    del incomplete["corpus_content_hash"]
    checks.append(("a result missing a required field fails validation", serialize.validate_against_result_schema(incomplete) != []))
    try:
        serialize.serialize_result(incomplete)
        checks.append(("serialize_result raises on an invalid result", False))
    except serialize.ResultValidationError:
        checks.append(("serialize_result raises on an invalid result", True))

    line = serialize.serialize_result(result)
    round_tripped = serialize.deserialize_result(line)
    checks.append(("round-trip serialize/deserialize preserves all values", round_tripped == result))
    checks.append(("round-trip preserves corpus_content_hash specifically", round_tripped["corpus_content_hash"] == result["corpus_content_hash"]))

    line2 = serialize.serialize_result(result)
    checks.append(("serialization is byte-reproducible for the same result dict", line == line2))

    # raw_response must round-trip as opaque data but never be consulted by serialize_result's
    # own validation logic (it isn't a required field).
    result_with_raw = dict(result, raw_response={"note": "opaque debugging payload"})
    line3 = serialize.serialize_result(result_with_raw)
    checks.append(("raw_response is passed through opaquely without being required or inspected",
                   serialize.deserialize_result(line3)["raw_response"] == {"note": "opaque debugging payload"}))

    with tempfile.TemporaryDirectory() as td:
        out_path = Path(td) / "results.jsonl"
        serialize.write_results_jsonl([result, result_with_raw], out_path)
        read_back = serialize.read_results_jsonl(out_path)
        checks.append(("write_results_jsonl + read_results_jsonl round-trips a batch", len(read_back) == 2 and read_back[0] == result))

        corpus_dir = Path(__file__).resolve().parents[2] / "corpus"
        try:
            serialize.write_results_jsonl([result], corpus_dir / "should_not_write.jsonl")
            checks.append(("write_results_jsonl refuses to write into laya/corpus/", False))
        except ValueError:
            checks.append(("write_results_jsonl refuses to write into laya/corpus/", True))
        checks.append(("the refused write did not actually create a file in laya/corpus/",
                       not (corpus_dir / "should_not_write.jsonl").exists()))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  serialization checks failed: {failed}")
        return 1
    print(f"PASS  serialization: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
