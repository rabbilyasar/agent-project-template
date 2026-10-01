#!/usr/bin/env bash
# Runs every deterministic self-test for the Phase 4.2 evaluation harness (Slice 1: corpus
# loader, prompt contracts, leakage preflight; Slice 2: deterministic prefilter, scoring,
# calibration, aggregation, serialization, end-to-end). Never invokes Claude, Laya, JEV, or
# any model/API.
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

run python3 "$script_dir/test_corpus_loader.py"
run python3 "$script_dir/test_prompt_contracts.py"
run python3 "$script_dir/test_leakage_preflight.py"
run python3 "$script_dir/test_deterministic_prefilter.py"
run python3 "$script_dir/test_score.py"
run python3 "$script_dir/test_calibration.py"
run python3 "$script_dir/test_aggregate_report.py"
run python3 "$script_dir/test_rescore_offline.py"
run python3 "$script_dir/test_serialize_result.py"
run python3 "$script_dir/test_end_to_end_deterministic.py"
run python3 "$script_dir/test_adapter_base.py"
run python3 "$script_dir/test_laya_adapter.py"
run python3 "$script_dir/test_deepseek_adapter.py"
run python3 "$script_dir/test_claude_adapter.py"

if [[ "$fail" -eq 0 ]]; then
    echo "All Phase 4.2 self-tests passed."
else
    echo "Some Phase 4.2 self-tests FAILED." >&2
fi
exit "$fail"
