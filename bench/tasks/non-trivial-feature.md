---
id: TASK-NON-TRIVIAL-FEATURE-001
class: non-trivial-feature
title: Implement REQ-010 rate limiting on /widgets
---

## Scenario / Setup

Starting repository: `bench/fixture` at its pinned commit, with the arm's template stamped in.
`docs/requirements.md` already contains REQ-010 (rate limit `/widgets` per client), marked
Accepted but not implemented.

## Prompt

> Implement REQ-010: rate limit `/widgets` to N requests per client per rolling minute, N
> configurable, returning HTTP 429 when exceeded.

## Expected Behavior

A working rate limiter wired into the `/widgets` handler, a configurable limit, correct 429
behavior, and — per this project's own process — a reference to REQ-010 in the change and an
update to `.agent/state.md`/`.agent/current-task.md` reflecting the work, plus the validation
chain actually run before reporting completion.

## Deterministic Validation

- A hidden acceptance test suite, supplied by the harness only during validation
  (`bench/harness/hidden_tests/non-trivial-feature/`), drives `/widgets` past the configured limit
  and asserts a 429 response, then asserts requests succeed again after the window rolls over.
- Existing test suite (`npm test`) still passes.
- `npm run typecheck` and `npm run lint` pass.

## Success Criteria

- Hidden acceptance tests pass.
- REQ-010 is referenced somewhere in the change (commit message is not required since commits
  aren't requested; the requirement ID appearing in code comments, `.agent/current-task.md`, or the
  final report is sufficient).
- No unrelated files are modified.

## Allowed File Scope

- `src/widgets.ts`, `src/server.ts`
- A new source file implementing the limiter, if the agent chooses to add one
- `test/*.test.ts` for any tests the agent adds
- `.agent/current-task.md`, `.agent/state.md`, `docs/requirements.md` (status update only)
