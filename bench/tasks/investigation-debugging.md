---
id: TASK-INVESTIGATION-DEBUGGING-001
class: investigation-debugging
title: Stale widget list returned after cache expiry
---

## Scenario / Setup

Starting repository: `bench/fixture` at its pinned commit (unmodified — the bug is already
present in `src/cache.ts`), with the arm's template stamped in. The agent is not told where the
bug lives.

## Prompt

> Users report that `/widgets` sometimes returns stale data for a client well after it should
> have refreshed. Investigate and fix the root cause.

## Expected Behavior

The agent reproduces or reasons through the symptom, locates the cause in the shared
`TtlCache.get()` (`src/cache.ts`) rather than patching each call site (`src/widgets.ts` and any
other caller), and fixes the expiry check in the one shared function.

## Deterministic Validation

- The existing suite (`npm test`) still passes.
- A hidden regression test, supplied by the harness only during validation
  (`bench/harness/hidden_tests/investigation-debugging/`), asserts that `TtlCache.get()` returns
  `undefined` once a key has expired. This test is not visible to the agent during the trial.
- A structural check confirms the diff touches `src/cache.ts` (the shared function) rather than
  duplicating an expiry check independently in every caller.

## Success Criteria

- Hidden regression test passes.
- Existing test suite still passes.
- Fix is located in `src/cache.ts`, not scattered across callers.

## Allowed File Scope

- `src/cache.ts`
- `test/cache.test.ts` (if the agent adds its own regression test — encouraged, not required)
- Caller files (`src/widgets.ts`) should not need to change for a correct root-cause fix; a change
  there is a signal the fix addressed a symptom, not the cause.
