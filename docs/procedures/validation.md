# Validation

This procedure defines how to gather verification evidence: deterministic checks and agent-gathered
evidence, in order. It is operational reference (see `AGENTS.md` — Source of Truth): consult it for
how to validate, not for what to build.

Look up this project's actual commands in `docs/development.md` rather than guessing or
rediscovering them each session.

Validation should match the scope and risk of the change. Use only the checks that apply, and mark
any that do not as N/A rather than pretending it was performed. Do not force the full sequence below
onto a trivial change.

Verification is evidence, not authority: a passing check shows the change behaves as intended, it
does not itself authorize proceeding to commit. See `docs/procedures/completion.md` for how
verification evidence relates to human acceptance.

## A. Deterministic Verification

Checks software can objectively verify. When relevant, use this order:

1. Formatter.
2. Linter.
3. Type checker.
4. Targeted unit tests.
5. Integration tests.

## B. Agent Verification

Evidence gathered through tools — browser/end-to-end flows, API or integration behavior,
screenshots, or other tool-based observation — for changes whose behavior can be meaningfully
verified this way.

When a change affects a user-visible web or browser flow:

- Verify the affected flow using the project's available browser testing tooling.
- Prefer the project's pinned Playwright version rather than a global installation.
- Reproduce failures before changing the implementation when practical.
- Inspect relevant browser diagnostics when a browser test fails.
- Fix the underlying issue rather than masking the failure.
- Rerun the affected flow after fixing it.

Do not launch browser tests for changes that cannot affect user-visible browser behavior unless
there is another clear reason to do so.

## Regression Validation

After the applicable checks above pass, run appropriate regression validation for the scope and
risk of the change.

## Evidence

Show the actual command or tool run and its actual output — not an assertion that a check was
performed or that it passed.
