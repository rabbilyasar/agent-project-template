# Completion

This procedure defines when non-trivial work is actually done. It is operational reference (see
`AGENTS.md` — Source of Truth): consult it for how to confirm completion, not for what to build.

A task is not complete merely because code was changed.

## Verification Tiers

Verification happens across up to three tiers. Use only the tiers that apply to the change; mark
any tier that does not apply as N/A rather than pretending it was performed:

- **Automated verification** — deterministic checks (see `docs/procedures/validation.md`).
- **Agent verification** — evidence gathered through tools (see `docs/procedures/validation.md`),
  used when the change affects behavior that can meaningfully be verified this way.
- **Human acceptance** — the user personally inspecting or using the result, required when the work
  needs human or product acceptance.

Automated and agent verification produce evidence that the change behaves as intended. They do not
themselves constitute human acceptance, and both passing never implies acceptance — only the user's
explicit acceptance does.

When reporting completion of non-trivial work, state the status of each applicable tier:

```
Automated verification: PASS/N/A/FAIL
Agent verification: PASS/N/A/FAIL
Human acceptance: PENDING/ACCEPTED/REJECTED/N/A
Commit: BLOCKED/PERMITTED
```

Commit stays BLOCKED until the applicable tiers pass and, where human acceptance applies, the user
has explicitly accepted — and even then, only after a separate, explicit commit request (see
`AGENTS.md` — Git).

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
