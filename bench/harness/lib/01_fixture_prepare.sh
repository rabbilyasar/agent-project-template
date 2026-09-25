#!/usr/bin/env bash
# Stage 1: fixture preparation.
#
# Copies bench/fixture into a fresh scratch directory. Pure file copy: no
# git init, no template, no agent involvement -- that separation happens in
# later stages so each can be tested independently. Copies the working tree
# directly rather than via `git archive`, since it must work whether or not
# bench/fixture has been committed yet; the orchestrator records the actual
# commit SHA separately as run metadata for provenance.
set -euo pipefail

usage() {
    printf 'Usage: %s <repo-root> <destination-dir>\n' "$(basename "$0")"
    printf 'Copies bench/fixture into <destination-dir> (must not exist).\n'
}

if [[ $# -ne 2 ]]; then
    usage >&2
    exit 2
fi

repo_root=$1
destination=$2
fixture_source="$repo_root/bench/fixture"

if [[ ! -d "$fixture_source" ]]; then
    printf 'Error: fixture source not found: %s\n' "$fixture_source" >&2
    exit 1
fi

if [[ -e "$destination" ]]; then
    printf 'Error: destination already exists: %s\n' "$destination" >&2
    exit 1
fi

mkdir -p "$destination"
cp -r "$fixture_source/." "$destination/"

printf 'Prepared fixture into: %s\n' "$destination"
