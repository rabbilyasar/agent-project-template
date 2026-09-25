# Validation

This procedure defines validation ordering and browser/end-to-end verification. It is operational
reference (see `AGENTS.md` — Source of Truth): consult it for how to validate, not for what to
build.

Look up this project's actual commands in `docs/development.md` rather than guessing or
rediscovering them each session.

Validation should match the scope and risk of the change.

## Ordering

When relevant, use this order:

1. Formatter.
2. Linter.
3. Type checker.
4. Targeted unit tests.
5. Integration tests.
6. Targeted browser or end-to-end verification for affected user-visible flows.
7. Regression validation.

Do not claim validation was performed when it was not.

If a validation step does not apply, state that explicitly when reporting completion.

## Browser Verification

When a change affects a user-visible web or browser flow:

- Verify the affected flow using the project's available browser testing tooling.
- Prefer the project's pinned Playwright version rather than a global installation.
- Reproduce failures before changing the implementation when practical.
- Inspect relevant browser diagnostics when a browser test fails.
- Fix the underlying issue rather than masking the failure.
- Rerun the affected flow after fixing it.
- Perform appropriate regression verification.

Do not launch browser tests for changes that cannot affect user-visible browser behavior unless
there is another clear reason to do so.
