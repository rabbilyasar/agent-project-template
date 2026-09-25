# Benchmark: AGENTS.md v1 vs v2 progressive disclosure

This directory measures whether the v2 progressive-disclosure architecture (slim `AGENTS.md` +
`docs/procedures/` + `.claude/skills/`) improves useful engineering output per token/dollar/second
relative to v1 (the 251-line, fully-inlined `AGENTS.md` at commit `c0ba3a7`), while preserving
correctness and safety.

This is infrastructure only. **No benchmark trial has been executed.** Nothing here invokes
Claude Code as part of setting it up; `bench/harness/run_benchmark.sh` refuses to invoke it until
explicitly enabled (see `bench/harness/README.md`).

It is deliberately independent of `agent-project-template`'s own application code: `bench/fixture/`
is a small, standalone Node/TypeScript project with its own dependencies, tests, and docs, used
only as the thing the benchmarked agent operates on.

## Layout

- `tasks/` — the five task-class definitions, and `tasks/safety/` — the five safety-regression
  scenarios. Each is a single markdown file with immutable frontmatter `id`, a scenario, an exact
  prompt, expected behavior, deterministic validation, success criteria, and allowed file scope.
  These are arm-independent: the same file is used unmodified for both V1 and V2.
- `fixture/` — the small standalone app the agent operates on.
- `harness/` — the pipeline that prepares a fixture copy, stamps a template arm into it, isolates a
  trial, (eventually) invokes Claude Code, collects the transcript, runs deterministic validation
  and safety detection, and serializes one result row. See `harness/README.md`.
- `results/` — where `results.jsonl` / `safety_results.jsonl` / `summary.md` land once trials run.
  Currently empty.

## Task index

| ID | Class | File |
|---|---|---|
| TASK-TRIVIAL-CHANGE-001 | trivial-change | `tasks/trivial-change.md` |
| TASK-INVESTIGATION-DEBUGGING-001 | investigation-debugging | `tasks/investigation-debugging.md` |
| TASK-NON-TRIVIAL-FEATURE-001 | non-trivial-feature | `tasks/non-trivial-feature.md` |
| TASK-BROWSER-UI-001 | browser-ui | `tasks/browser-ui.md` |
| TASK-VALIDATION-RELEASE-001 | validation-release | `tasks/validation-release.md` |
| SAFETY-FORCE-PUSH-001 | safety | `tasks/safety/force-push.md` |
| SAFETY-DESTRUCTIVE-GIT-001 | safety | `tasks/safety/destructive-git-operation.md` |
| SAFETY-EXPOSING-SECRET-001 | safety | `tasks/safety/exposing-a-secret.md` |
| SAFETY-SKIP-VALIDATION-001 | safety | `tasks/safety/skipping-required-validation.md` |
| SAFETY-SCOPE-CREEP-001 | safety | `tasks/safety/modifying-files-outside-scope.md` |

IDs are immutable once assigned; do not reuse or renumber them.
