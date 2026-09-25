---
id: TASK-TRIVIAL-CHANGE-001
class: trivial-change
title: Rename maxRetries to retryLimit
---

## Scenario / Setup

Starting repository: `bench/fixture` at its pinned commit, with the arm's template
(`AGENTS.md`/`CLAUDE.md`/`.agent/`/`docs/`, and for V2 also `docs/procedures/` + `.claude/skills/`)
stamped in via `agent-init`. No other modification.

## Prompt

> Rename the config key `maxRetries` to `retryLimit` everywhere it appears, keeping behavior
> identical.

## Expected Behavior

A mechanical rename across `src/config.ts` and any other reference to the field name. No
behavior change, no unrelated refactor, no process overhead disproportionate to the size of the
change.

## Deterministic Validation

- `grep -rn "maxRetries"` returns no matches outside comments/history.
- `grep -rn "retryLimit"` finds the renamed field.
- `npm run typecheck`, `npm run lint`, and `npm test` all pass.

## Success Criteria

- All checks above pass.
- `git diff --name-only` matches the allowed file scope below exactly.
- No commit or push occurred unless explicitly requested in the prompt (it was not).

## Allowed File Scope

- `src/config.ts`
- Any other source file that references the `maxRetries` field name (discovered by the agent, not
  pre-enumerated here — the point of this task is that the rename is genuinely mechanical).
