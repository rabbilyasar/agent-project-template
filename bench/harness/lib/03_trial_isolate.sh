#!/usr/bin/env bash
# Stage 3: trial isolation.
#
# Turns a fixture+template directory (stages 1-2's output) into a realistic,
# isolated git repository: an initial commit and a local bare "origin"
# remote, so tasks that involve git (including the safety scenarios) have
# something real to operate on. Also creates a fresh, empty directory for
# this trial to use as CLAUDE_CONFIG_DIR (see lib/04_invoke_claude.sh and
# harness/README.md for the verified isolation mechanism). This directory
# must be unique per trial and never reused -- reusing it would carry
# session history/auto-memory from one trial into the next.
set -euo pipefail

usage() {
    printf 'Usage: %s <trial-dir> <claude-config-dir>\n' "$(basename "$0")"
    printf 'Git-initializes <trial-dir> with an initial commit and a local origin remote, and\n'
    printf 'creates an empty <claude-config-dir> for this trial.\n'
}

if [[ $# -ne 2 ]]; then
    usage >&2
    exit 2
fi

trial_dir=$1
claude_config_dir=$2

if [[ ! -d "$trial_dir" ]]; then
    printf 'Error: trial dir does not exist (run stages 1-2 first): %s\n' "$trial_dir" >&2
    exit 1
fi

git -C "$trial_dir" init -q
git -C "$trial_dir" config user.email "bench@example.invalid"
git -C "$trial_dir" config user.name "bench"
git -C "$trial_dir" add -A
git -C "$trial_dir" commit -q -m "bench: initial fixture state"

remote_dir="$trial_dir.origin.git"
rm -rf "$remote_dir"
git init -q --bare "$remote_dir"
git -C "$trial_dir" remote add origin "$remote_dir"
git -C "$trial_dir" push -q -u origin HEAD:refs/heads/main

if [[ -e "$claude_config_dir" ]]; then
    printf 'Error: claude_config_dir must not already exist (must be fresh per trial): %s\n' \
        "$claude_config_dir" >&2
    exit 1
fi
mkdir -p "$claude_config_dir"

printf 'Isolated trial at: %s (origin: %s)\n' "$trial_dir" "$remote_dir"
printf 'Fresh CLAUDE_CONFIG_DIR for this trial: %s\n' "$claude_config_dir"
