#!/usr/bin/env bash
# Orchestrates lib/01..08 in order for one (task, arm, trial). A plain
# top-to-bottom pipeline, not a router or dynamic dispatcher.
#
# Refuses to reach stage 4 (Claude Code invocation) unless
# BENCH_ALLOW_CLAUDE_INVOKE=1 is set -- this benchmark is infrastructure
# only until that is deliberately turned on. See harness/README.md.
set -euo pipefail

usage() {
    printf 'Usage: %s <repo-root> <task-id> <arm:v1|v2> <trial-id> <work-dir>\n' "$(basename "$0")"
    printf 'Runs one (task, arm, trial). Requires BENCH_ALLOW_CLAUDE_INVOKE=1 to reach stage 4.\n'
}

if [[ $# -ne 5 ]]; then
    usage >&2
    exit 2
fi

repo_root=$1
task_id=$2
arm=$3
trial_id=$4
work_dir=$5
lib="$repo_root/bench/harness/lib"

fixture_commit="$(git -C "$repo_root" rev-parse HEAD)"
trial_dir="$work_dir/trial"
claude_config_dir="$work_dir/claude-config"
transcript_out="$work_dir/transcript.json"
prompt_file="$work_dir/prompt.txt"
result_file="$work_dir/result.json"

mkdir -p "$work_dir"

echo "== stage 1: fixture prepare =="
"$lib/01_fixture_prepare.sh" "$repo_root" "$trial_dir"

echo "== stage 2: stamp template ($arm) =="
"$lib/02_stamp_template.sh" "$repo_root" "$arm" "$trial_dir"

echo "== stage 3: trial isolate =="
"$lib/03_trial_isolate.sh" "$trial_dir" "$claude_config_dir"

echo "== stage 4: invoke claude =="
if [[ "${BENCH_ALLOW_CLAUDE_INVOKE:-0}" != "1" ]]; then
    echo "SKIPPED: Claude invocation disabled during scaffolding (see bench/harness/README.md)."
    echo "Set BENCH_ALLOW_CLAUDE_INVOKE=1 to enable once stage 4 is wired up."
    exit 0
fi
"$lib/04_invoke_claude.sh" "$trial_dir" "$claude_config_dir" "$prompt_file" "$transcript_out"

echo "== stage 5: collect transcript =="
python3 "$lib/05_collect_transcript.py" "$transcript_out" > "$work_dir/metrics.json"

echo "== stage 6: validate =="
"$lib/06_validate.sh" "$repo_root" "$task_id" "$trial_dir" > "$work_dir/validation_result.json"

echo "== stage 7: safety detect =="
python3 "$lib/07_safety_detect.py" "$transcript_out" > "$work_dir/safety_result.json"

echo "== stage 8: serialize result =="
python3 - "$work_dir" "$task_id" "$arm" "$trial_id" "$fixture_commit" <<'PYEOF' > "$result_file"
import json, sys
from datetime import datetime, timezone
from pathlib import Path

work_dir, task_id, arm, trial_id, fixture_commit = sys.argv[1:6]
metrics = json.loads((Path(work_dir) / "metrics.json").read_text())
validation_result = json.loads((Path(work_dir) / "validation_result.json").read_text())
safety_result = json.loads((Path(work_dir) / "safety_result.json").read_text())

record = {
    "task_id": task_id,
    "arm": arm,
    "trial_id": int(trial_id),
    "fixture_commit": fixture_commit,
    "template_commit": "c0ba3a7" if arm == "v1" else "working-tree",
    "model_id": "UNSET",
    "claude_code_version": "UNSET",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "validation_result": validation_result,
    "safety_result": safety_result,
    **metrics,
}
json.dump(record, sys.stdout)
PYEOF

"$lib/08_serialize_result.py" "$result_file" "$repo_root/bench/results/results.jsonl"

echo "Result appended to bench/results/results.jsonl"
