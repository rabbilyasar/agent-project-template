#!/usr/bin/env python3
"""Deterministic self-test: every bench/tasks/*.md file is complete.

Does not invoke Claude Code. Checks:
  - frontmatter has non-empty id/class/title
  - all required sections are present
  - task IDs are unique across the whole task set
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = (
    "## Scenario / Setup",
    "## Prompt",
    "## Expected Behavior",
    "## Deterministic Validation",
    "## Success Criteria",
    "## Allowed File Scope",
)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing frontmatter block")
    fields = {}
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def check_task_file(path: Path) -> list[str]:
    errors = []
    text = path.read_text(encoding="utf-8")

    try:
        frontmatter = parse_frontmatter(text)
    except ValueError as exc:
        return [f"{path}: {exc}"]

    for key in ("id", "class", "title"):
        if not frontmatter.get(key):
            errors.append(f"{path}: frontmatter missing non-empty '{key}'")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"{path}: missing required section '{section}'")

    return errors


def main() -> int:
    repo_root = Path(__file__).resolve().parents[3]
    tasks_dir = repo_root / "bench" / "tasks"
    task_files = sorted(tasks_dir.glob("*.md")) + sorted((tasks_dir / "safety").glob("*.md"))

    if not task_files:
        print("FAIL  no task definition files found")
        return 1

    errors: list[str] = []
    ids: dict[str, Path] = {}

    for path in task_files:
        errors.extend(check_task_file(path))
        try:
            frontmatter = parse_frontmatter(path.read_text(encoding="utf-8"))
        except ValueError:
            continue
        task_id = frontmatter.get("id")
        if task_id:
            if task_id in ids:
                errors.append(f"{path}: duplicate id '{task_id}' also used by {ids[task_id]}")
            ids[task_id] = path

    if errors:
        for error in errors:
            print(f"FAIL  {error}")
        return 1

    print(f"PASS  {len(task_files)} task definitions are complete and IDs are unique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
