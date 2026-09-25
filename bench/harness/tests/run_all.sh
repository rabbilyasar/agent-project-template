#!/usr/bin/env bash
# Runs every deterministic self-test for the benchmark infrastructure.
# Never invokes Claude Code.
set -uo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
fail=0

run() {
    echo "== $1 =="
    if "$@"; then
        :
    else
        fail=1
    fi
    echo
}

run python3 "$script_dir/test_task_definitions.py"
run bash "$script_dir/test_fixture_bootstrap.sh"
run bash "$script_dir/test_isolation_config.sh"
run python3 "$script_dir/test_transcript_parser.py"
run python3 "$script_dir/test_safety_detect.py"

if [[ "$fail" -eq 0 ]]; then
    echo "All benchmark infrastructure self-tests passed."
else
    echo "Some benchmark infrastructure self-tests FAILED." >&2
fi
exit "$fail"
