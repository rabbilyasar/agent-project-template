#!/usr/bin/env python3
"""Unit test for lib/05_collect_transcript.py against a small synthetic
transcript authored by hand -- no real Claude Code run is involved."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_collect_transcript():
    lib_path = Path(__file__).resolve().parents[1] / "lib" / "05_collect_transcript.py"
    spec = importlib.util.spec_from_file_location("collect_transcript", lib_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = _load_collect_transcript()
    sample_path = Path(__file__).resolve().parent / "fixtures" / "sample_transcript.json"
    transcript = json.loads(sample_path.read_text(encoding="utf-8"))

    result = module.collect(transcript)

    checks = [
        ("input_tokens", result["input_tokens"] == 1200),
        ("output_tokens", result["output_tokens"] == 160),
        ("cache_read_tokens", result["cache_read_tokens"] == 1350),
        ("cache_write_tokens", result["cache_write_tokens"] == 0),
        ("tool_calls Read", result["tool_calls"].get("Read") == 1),
        ("tool_calls Edit", result["tool_calls"].get("Edit") == 1),
        ("tool_calls Bash", result["tool_calls"].get("Bash") == 1),
        ("files_read", result["files_read"] == ["src/config.ts"]),
        ("files_modified", result["files_modified"] == ["src/config.ts"]),
        ("wall_time", result["wall_time"] == 15.0),
        ("human_intervention_count", result["human_intervention_count"] == 0),
    ]

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  transcript parser checks failed: {failed}")
        print(json.dumps(result, indent=2))
        return 1

    print(f"PASS  transcript parser: {len(checks)} checks against sample_transcript.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
