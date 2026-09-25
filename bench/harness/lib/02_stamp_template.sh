#!/usr/bin/env bash
# Stage 2: template stamping.
#
# Installs the requested arm's template into an already-prepared fixture
# directory (stage 1's output) via the existing, already-tested
# bin/agent-init-install + bin/agent-init pipeline -- no new stamping logic.
#
# v1 = the template as committed at $V1_TEMPLATE_REF (default: c0ba3a7),
#      checked out into a disposable worktree first, since that ref predates
#      docs/procedures/ and .claude/.
# v2 = the template as it currently stands in the repo's working tree
#      (uncommitted changes included), since v2 has not been committed yet.
set -euo pipefail

usage() {
    printf 'Usage: %s <repo-root> <v1|v2> <target-dir>\n' "$(basename "$0")"
    printf 'Stamps the AGENTS.md template for the given arm into <target-dir> (agent-init never\n'
    printf 'overwrites files that already exist there, e.g. the fixture'"'"'s own docs).\n'
    printf '\n'
    printf 'Env: V1_TEMPLATE_REF (default: c0ba3a7)\n'
}

if [[ $# -ne 3 ]]; then
    usage >&2
    exit 2
fi

repo_root=$1
arm=$2
target_dir=$3
v1_template_ref="${V1_TEMPLATE_REF:-c0ba3a7}"

if [[ "$arm" != "v1" && "$arm" != "v2" ]]; then
    printf 'Error: arm must be v1 or v2, got: %s\n' "$arm" >&2
    exit 2
fi

if [[ ! -d "$target_dir" ]]; then
    printf 'Error: target dir does not exist (run stage 1 first): %s\n' "$target_dir" >&2
    exit 1
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fake_home="$work/home"
mkdir -p "$fake_home"

if [[ "$arm" == "v1" ]]; then
    v1_checkout="$work/v1-checkout"
    git -C "$repo_root" worktree add --detach "$v1_checkout" "$v1_template_ref" >/dev/null
    trap 'git -C "'"$repo_root"'" worktree remove --force "'"$v1_checkout"'" >/dev/null 2>&1 || true; rm -rf "$work"' EXIT
    installer="$v1_checkout/bin/agent-init-install"
else
    installer="$repo_root/bin/agent-init-install"
fi

HOME="$fake_home" "$installer" >/dev/null

template_dir="$fake_home/.local/share/agent-init"
AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$target_dir" >/dev/null

printf 'Stamped %s template into: %s\n' "$arm" "$target_dir"
