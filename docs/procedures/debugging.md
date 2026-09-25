# Debugging

This procedure defines how to investigate and fix a reported defect: reproduce, gather evidence,
isolate, identify the root cause, then make the smallest fix that addresses it. It is operational
reference (see `AGENTS.md` — Source of Truth): consult it for how to debug, not for what to build.

## When this applies

Use this procedure when investigating a reported or observed defect. Do not force it onto trivial
changes with no meaningful investigation.

If an existing project-specific or third-party debugging skill is available and appropriate for the
situation, use it instead of duplicating it here — this procedure is the vendor-neutral fallback.

## Lifecycle

1. **Report** — Start from the reported symptom, not an assumed cause.
2. **Reproduce / confirm** — Reproduce the failure, or otherwise confirm it actually occurs, before
   modifying production code whenever reasonably possible.
3. **Observe evidence** — Gather concrete evidence (output, logs, a failing test) rather than
   reasoning from assumption.
4. **Isolate** — Narrow the failure to the smallest reproducing case or the specific component
   responsible.
5. **Identify root cause** — State the root cause explicitly before finalizing a fix. Do not patch
   a symptom merely because the failure happens to surface at a particular call site; find the
   actual defect. Before declaring behavior a defect, check relevant project specifications,
   decisions, and documented limitations for an intentional rationale — a documented limitation is
   not the same as an oversight.
6. **Add or update a regression test** — When the defect is reasonably testable, add or update a
   test that fails before the fix and passes after it.
7. **Make the smallest appropriate fix** — Fix the identified root cause with the smallest change
   that addresses it. Do not perform unrelated cleanup or refactoring while debugging unless it is
   necessary for the fix itself.
8. **Verify** — See `docs/procedures/validation.md` for ordering. Do not claim the defect is fixed
   without evidence.
9. **Report root cause, fix, and evidence** — State the root cause, the fix, and the evidence that
   confirms it, distinguishing observed behavior, hypothesis, confirmed root cause, and verified
   fix from one another.

## When it cannot be reproduced

If the failure cannot be reproduced or confirmed, do not report it as fixed. Report what was
investigated and what evidence was actually obtained.

## Scope

A broad or expensive investigation may warrant a subagent, but ordinary debugging does not require
one.
