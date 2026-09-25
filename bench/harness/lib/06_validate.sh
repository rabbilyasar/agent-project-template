#!/usr/bin/env bash
# Stage 6: deterministic validation.
#
# Copies the task's hidden validation assets (never shown to the agent
# during the trial) into the trial directory, then independently re-runs the
# fixture's real validation chain plus any task-specific hidden test. Never
# trusts the agent's own transcript claim that validation passed -- results
# here come only from actually executing the commands.
set -euo pipefail

usage() {
    printf 'Usage: %s <repo-root> <task-id> <trial-dir>\n' "$(basename "$0")"
    printf 'Writes a JSON validation_result object (see schema/result_schema.json) to stdout.\n'
}

if [[ $# -ne 3 ]]; then
    usage >&2
    exit 2
fi

repo_root=$1
task_id=$2
trial_dir=$3

hidden_dir="$repo_root/bench/harness/hidden_tests/$task_id"
if [[ -d "$hidden_dir" ]]; then
    cp -r "$hidden_dir/." "$trial_dir/"
fi

steps_json="[]"
overall_passed=true

run_step() {
    local name=$1
    shift
    local passed="true"
    local detail=""
    if ! detail="$(cd "$trial_dir" && "$@" 2>&1)"; then
        passed="false"
        overall_passed=false
    fi
    steps_json="$(printf '%s' "$steps_json" | python3 -c '
import json, sys
steps = json.load(sys.stdin)
steps.append({"name": sys.argv[1], "passed": sys.argv[2] == "true", "detail": sys.argv[3]})
json.dump(steps, sys.stdout)
' "$name" "$passed" "$detail")"
}

if [[ -f "$trial_dir/package.json" ]]; then
    run_step "format:check" npm run --silent format:check
    run_step "lint" npm run --silent lint
    run_step "typecheck" npm run --silent typecheck
    run_step "test" npm run --silent test
    if [[ -f "$trial_dir/playwright.config.ts" && -d "$hidden_dir" ]]; then
        run_step "e2e" npm run --silent e2e
    fi
fi

python3 -c '
import json, sys
print(json.dumps({"steps": json.loads(sys.argv[1]), "overall_passed": sys.argv[2] == "true"}))
' "$steps_json" "$overall_passed"
