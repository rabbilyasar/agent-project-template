# Results

Empty until a benchmark trial actually runs. `run_benchmark.sh` will write:

- `results.jsonl` — one row per `(task, arm, trial)` for the five task-class benchmarks, matching
  `bench/harness/schema/result_schema.json`.
- `safety_results.jsonl` — one row per `(safety scenario, arm, trial)`.
- `summary.md` — a generated markdown table of medians per task class/arm, produced by a small
  script over the two JSONL files above (not built yet — there is nothing to summarize until
  trials exist).

No dashboard is planned; JSONL plus a generated markdown summary is the intended end state.
