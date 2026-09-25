#!/usr/bin/env bash
# Stage 4: Claude Code invocation.
#
# NOT CALLED by anything in this repository yet. run_benchmark.sh only
# reaches this stage when BENCH_ALLOW_CLAUDE_INVOKE=1 is set, and this script
# additionally refuses to run without it, so a benchmark trial cannot happen
# by accident while this is still infrastructure.
#
# Isolation mechanism (verified against installed Claude Code 2.1.282 on
# 2026-09-25 -- see harness/README.md for how this was checked):
#
#   CLAUDE_CONFIG_DIR=<fresh, never-reused dir> \
#     claude --setting-sources project -p "<prompt>" --output-format json \
#            --permission-mode bypassPermissions
#
# run with cwd = <trial-dir>. CLAUDE_CONFIG_DIR redirects Claude Code's
# entire user-level state (settings.json, plugins, credentials, session
# history, built-in auto-memory) away from the operator's real ~/.claude, so
# no personal plugin (ponytail, superpowers, ...), no personal hook, and no
# prior session's memory can reach the trial. --setting-sources project is
# the officially documented, narrower complement: it excludes the user and
# local settings scopes explicitly, so even if the fresh config dir ever
# picked up an unexpected settings.json, plugin-derived settings still
# couldn't apply. Neither --bare nor --safe-mode is used: --safe-mode
# disables project skills outright, and --bare removes the Skill tool from
# the tool set entirely (see harness/README.md) -- both would break the very
# V2 mechanism this benchmark measures.
#
# --permission-mode bypassPermissions is required because this runs
# non-interactively with no human to answer a permission prompt; there is no
# other way to make progress in headless mode. This means the safety suite
# (bench/tasks/safety/) is testing the MODEL's own judgment (does it choose
# to ask via AskUserQuestion, or refuse) -- not the permission system, which
# is deliberately wide open here. Keep this in mind when interpreting results.
#
# Auth: a fresh CLAUDE_CONFIG_DIR has no credentials file, so OAuth/keychain
# login (which lives under the operator's real ~/.claude) will not work here.
# Set ANTHROPIC_API_KEY (or an apiKeyHelper via --settings) before running a
# real trial -- this is a prerequisite, not something this script can supply.
set -euo pipefail

usage() {
    printf 'Usage: %s <trial-dir> <claude-config-dir> <prompt-file> <transcript-out>\n' "$(basename "$0")"
    printf 'Requires BENCH_ALLOW_CLAUDE_INVOKE=1 and ANTHROPIC_API_KEY (or --settings apiKeyHelper).\n'
}

if [[ "${BENCH_ALLOW_CLAUDE_INVOKE:-0}" != "1" ]]; then
    printf 'Refusing to invoke Claude Code: BENCH_ALLOW_CLAUDE_INVOKE is not set to 1.\n' >&2
    printf 'This benchmark is still infrastructure-only -- see bench/harness/README.md.\n' >&2
    exit 1
fi

if [[ $# -ne 4 ]]; then
    usage >&2
    exit 2
fi

trial_dir=$1
claude_config_dir=$2
prompt_file=$3
transcript_out=$4

if [[ "$claude_config_dir" == "$HOME/.claude" ]]; then
    printf 'Refusing: claude_config_dir must not be the operator'"'"'s real ~/.claude.\n' >&2
    exit 1
fi

mkdir -p "$claude_config_dir"

(
    cd "$trial_dir"
    CLAUDE_CONFIG_DIR="$claude_config_dir" claude \
        --setting-sources project \
        --permission-mode bypassPermissions \
        --output-format json \
        -p "$(cat "$prompt_file")" \
        > "$transcript_out"
)

printf 'Transcript written to: %s\n' "$transcript_out"
