#!/usr/bin/env bash
# Deterministic self-test: stages 1-2 actually produce a working v1 and v2
# trial directory from the real template. Does not invoke Claude Code and
# does not run stage 3+ (no git isolation, no trial semantics needed here --
# this only proves the fixture can be initialized with both template
# versions).
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
lib="$repo_root/bench/harness/lib"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fail=0
pass() { printf 'PASS  %s\n' "$1"; }
fail_() { printf 'FAIL  %s\n' "$1"; fail=1; }

for arm in v1 v2; do
    target="$work/$arm"
    if "$lib/01_fixture_prepare.sh" "$repo_root" "$target" >/dev/null; then
        pass "stage 1 prepares a $arm fixture directory"
    else
        fail_ "stage 1 prepares a $arm fixture directory"
        continue
    fi

    if [[ -f "$target/package.json" && -f "$target/src/config.ts" ]]; then
        pass "$arm fixture directory contains fixture source"
    else
        fail_ "$arm fixture directory contains fixture source"
    fi

    if "$lib/02_stamp_template.sh" "$repo_root" "$arm" "$target" >/dev/null; then
        pass "stage 2 stamps the $arm template"
    else
        fail_ "stage 2 stamps the $arm template"
        continue
    fi

    if [[ -f "$target/AGENTS.md" && -f "$target/CLAUDE.md" ]]; then
        pass "$arm trial dir has AGENTS.md and CLAUDE.md"
    else
        fail_ "$arm trial dir has AGENTS.md and CLAUDE.md"
    fi

    # The fixture ships its own docs/requirements.md and docs/decisions.md;
    # agent-init must never overwrite them (existing "never overwrite"
    # behavior), so their fixture content must survive stamping.
    if grep -q "REQ-010" "$target/docs/requirements.md" 2>/dev/null; then
        pass "$arm trial dir keeps the fixture's own docs/requirements.md"
    else
        fail_ "$arm trial dir keeps the fixture's own docs/requirements.md"
    fi

    if [[ "$arm" == "v1" ]]; then
        if [[ ! -d "$target/.claude" && ! -d "$target/docs/procedures" ]]; then
            pass "v1 trial dir has no .claude/ or docs/procedures/ (matches c0ba3a7)"
        else
            fail_ "v1 trial dir has no .claude/ or docs/procedures/ (matches c0ba3a7)"
        fi
    else
        if [[ -f "$target/.claude/skills/task-execution/SKILL.md" && -f "$target/docs/procedures/task-execution.md" ]]; then
            pass "v2 trial dir has .claude/skills/ and docs/procedures/"
        else
            fail_ "v2 trial dir has .claude/skills/ and docs/procedures/"
        fi
    fi
done

echo
if [[ "$fail" -eq 0 ]]; then
    echo "All fixture bootstrap checks passed."
else
    echo "Some fixture bootstrap checks FAILED." >&2
fi
exit "$fail"
