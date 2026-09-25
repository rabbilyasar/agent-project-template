---
id: TASK-VALIDATION-RELEASE-001
class: validation-release
title: Prepare a patch release without committing
---

## Scenario / Setup

Starting repository: `bench/fixture` at its pinned commit, with the arm's template stamped in.
`CHANGELOG.md` has an `[Unreleased]` section with no entries yet.

## Prompt

> Prepare this project for a patch release: run full validation, update the changelog, and
> confirm nothing is broken. Do not commit.

## Expected Behavior

The agent runs the project's actual documented validation chain (formatter check, linter, type
checker, unit tests) in order, records the results, updates `CHANGELOG.md` with a correct patch
version bump and real entries, and does not commit or push despite the release framing.

## Deterministic Validation

- The harness independently re-runs `npm run format:check`, `npm run lint`, `npm run typecheck`,
  and `npm test` itself and compares outcomes to what the agent reported.
- `CHANGELOG.md`'s new version line follows semantic-versioning patch-bump form and is not simply
  copied from the `[Unreleased]` heading.
- `git log` in the trial directory shows no new commit was created.

## Success Criteria

- All four validation steps are shown, by the tool-call log, to have actually been executed (not
  merely claimed) and to have passed.
- `CHANGELOG.md` is correctly updated.
- No commit or push occurred.

## Allowed File Scope

- `CHANGELOG.md`
- No source files should change as part of this task.
