#!/usr/bin/env bash
# Deterministic self-test: the isolation mechanism is wired correctly.
# Does NOT invoke the `claude` binary -- it only checks (a) that stage 3
# actually produces a fresh, unique, empty directory suitable for
# CLAUDE_CONFIG_DIR, and (b) that stage 4's invocation source actually uses
# CLAUDE_CONFIG_DIR + --setting-sources project and never references the
# operator's real $HOME/.claude. This tests the harness's own logic, not
# whether the installed Claude Code CLI honors the mechanism -- that was
# checked manually (see harness/README.md) and is out of scope for an
# automated, environment-independent test.
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
lib="$repo_root/bench/harness/lib"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fail=0
pass() { printf 'PASS  %s\n' "$1"; }
fail_() { printf 'FAIL  %s\n' "$1"; fail=1; }

# --- stage 3 actually produces a fresh, empty, unique config dir ---

trial_dir="$work/trial"
config_dir_a="$work/claude-config-a"
config_dir_b="$work/claude-config-b"

"$lib/01_fixture_prepare.sh" "$repo_root" "$trial_dir" >/dev/null
"$lib/02_stamp_template.sh" "$repo_root" v2 "$trial_dir" >/dev/null
"$lib/03_trial_isolate.sh" "$trial_dir" "$config_dir_a" >/dev/null

if [[ -d "$config_dir_a" ]]; then
    pass "stage 3 creates the requested config dir"
else
    fail_ "stage 3 creates the requested config dir"
fi

if [[ -z "$(ls -A "$config_dir_a" 2>/dev/null)" ]]; then
    pass "config dir is empty (no inherited settings/plugins/credentials/history)"
else
    fail_ "config dir is empty (no inherited settings/plugins/credentials/history)"
fi

if [[ "$config_dir_a" != "$HOME/.claude" ]]; then
    pass "config dir is not the operator's real \$HOME/.claude"
else
    fail_ "config dir is not the operator's real \$HOME/.claude"
fi

# A second trial must get a different, equally fresh directory -- stage 3
# must refuse to reuse an existing one, which is what "never reused" depends
# on structurally, not just by convention.
if "$lib/03_trial_isolate.sh" "$trial_dir" "$config_dir_a" >/dev/null 2>&1; then
    fail_ "stage 3 refuses to reuse an already-existing config dir"
else
    pass "stage 3 refuses to reuse an already-existing config dir"
fi

trial_dir_2="$work/trial-2"
"$lib/01_fixture_prepare.sh" "$repo_root" "$trial_dir_2" >/dev/null
"$lib/02_stamp_template.sh" "$repo_root" v2 "$trial_dir_2" >/dev/null
"$lib/03_trial_isolate.sh" "$trial_dir_2" "$config_dir_b" >/dev/null

if [[ "$config_dir_a" != "$config_dir_b" ]]; then
    pass "two trials get distinct config directories"
else
    fail_ "two trials get distinct config directories"
fi

# --- stage 4's invocation source uses the verified mechanism ---

invoke_script="$lib/04_invoke_claude.sh"

if grep -q 'CLAUDE_CONFIG_DIR="\$claude_config_dir"' "$invoke_script"; then
    pass "invocation sets CLAUDE_CONFIG_DIR from the per-trial config dir"
else
    fail_ "invocation sets CLAUDE_CONFIG_DIR from the per-trial config dir"
fi

if grep -q -- '--setting-sources project' "$invoke_script"; then
    pass "invocation passes --setting-sources project"
else
    fail_ "invocation passes --setting-sources project"
fi

# Only the actual invocation code should be checked for --bare/--safe-mode,
# not the comment block above it that explains why they are rejected.
invocation_code="$(grep -v '^\s*#' "$invoke_script")"

if grep -qE -- '--bare|--safe-mode' <<<"$invocation_code"; then
    fail_ "invocation must not use --bare or --safe-mode (both break the Skill tool/project skills)"
else
    pass "invocation does not use --bare or --safe-mode"
fi

if grep -q '"\$claude_config_dir" == "\$HOME/.claude"' "$invoke_script"; then
    pass "invocation refuses to run against the operator's real \$HOME/.claude"
else
    fail_ "invocation refuses to run against the operator's real \$HOME/.claude"
fi

echo
if [[ "$fail" -eq 0 ]]; then
    echo "All isolation config checks passed."
else
    echo "Some isolation config checks FAILED." >&2
fi
exit "$fail"
