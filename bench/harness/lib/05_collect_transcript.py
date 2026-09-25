#!/usr/bin/env python3
"""Stage 5: transcript/usage collection.

Parses a Claude Code `--output-format json` transcript (a list of message
objects) into the metrics this benchmark records. Deterministic, stdlib
only, and unit-tested against a small synthetic transcript in
harness/tests/fixtures/sample_transcript.json -- no real Claude Code run is
needed to exercise this parser.

Expected transcript shape (subset of Claude Code's JSON output actually
used here): a JSON array of message objects, each optionally containing:
  - "role": "assistant" | "user" | "system"
  - "usage": {"input_tokens": int, "output_tokens": int,
              "cache_read_input_tokens": int, "cache_creation_input_tokens": int}
  - "content": a list of blocks, where a tool_use block has
    {"type": "tool_use", "name": str, "input": {...}}
  - "timestamp": ISO-8601 string
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def collect(transcript: list[dict]) -> dict:
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_write_tokens = 0
    tool_calls: dict[str, int] = {}
    files_read: set[str] = set()
    files_modified: set[str] = set()
    human_intervention_count = 0
    timestamps: list[datetime] = []

    read_tools = {"Read", "Grep", "Glob"}
    write_tools = {"Edit", "Write"}
    file_arg_keys = ("file_path", "path")

    for message in transcript:
        ts = message.get("timestamp")
        if ts:
            timestamps.append(_parse_timestamp(ts))

        usage = message.get("usage") or {}
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)
        cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        cache_write_tokens += usage.get("cache_creation_input_tokens", 0)

        for block in message.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "unknown")
            tool_calls[name] = tool_calls.get(name, 0) + 1

            if name == "AskUserQuestion":
                human_intervention_count += 1

            tool_input = block.get("input") or {}
            for key in file_arg_keys:
                if key in tool_input:
                    if name in read_tools:
                        files_read.add(tool_input[key])
                    elif name in write_tools:
                        files_modified.add(tool_input[key])

    wall_time = 0.0
    if len(timestamps) >= 2:
        wall_time = (max(timestamps) - min(timestamps)).total_seconds()

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "tool_calls": tool_calls,
        "files_read": sorted(files_read),
        "files_modified": sorted(files_modified),
        "wall_time": wall_time,
        "human_intervention_count": human_intervention_count,
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} <transcript.json>", file=sys.stderr)
        return 2

    with open(argv[1], encoding="utf-8") as fh:
        transcript = json.load(fh)

    print(json.dumps(collect(transcript), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
