# Completion

This procedure defines when non-trivial work is actually done. It is operational reference (see
`AGENTS.md` — Source of Truth): consult it for how to confirm completion, not for what to build.

A task is not complete merely because code was changed.

Before reporting completion:

- Verify the requested behavior.
- Confirm relevant acceptance criteria.
- Run relevant validation.
- Review the final diff.
- Check for unintended changes.
- Update `.agent/state.md` when durable project state changed.
- Update relevant documentation when durable knowledge changed.
- Identify remaining concerns, limitations, or unvalidated areas.

## Definition of Done

For non-trivial tasks, the Definition of Done is:

- The requested behavior is implemented.
- Relevant requirements and acceptance criteria are satisfied.
- Relevant tests are added or updated when appropriate.
- Relevant validation passes.
- Affected user-visible flows are verified when applicable.
- The final diff has been reviewed.
- Required project documentation is updated.
- `.agent/state.md` reflects the new project state when appropriate.
- Remaining concerns are explicitly identified.
