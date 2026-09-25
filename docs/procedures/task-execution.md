# Task Execution

This procedure defines how to carry out non-trivial work: a staged sequence of investigate,
propose, approve, implement, verify, and stop for acceptance. It is operational reference (see
`AGENTS.md` — Source of Truth): consult it for how to execute a task, not for what to build.

## When this applies

Use the full staged sequence below for non-trivial, multi-file, or production-risk work. Skip it
for a change whose diff could genuinely be described in one sentence (a typo, a log line, a single
rename) — implement those directly. Do not force trivial changes through every stage, and do not
turn this into an approval gate for every individual action.

## 1. Investigate

Inspect the relevant code, tests, and documentation before proposing anything. Do not modify files
during investigation. Establish the actual problem or request and the constraints that apply.

## 2. Propose

State a narrow plan: what will change, and just as importantly, what will not. Do not begin
implementation yet.

## 3. Wait for explicit approval

Do not proceed past the proposal until the user has explicitly approved the proposed scope. Treat
that approved scope — not the original request, not anything discussed afterward — as the source
of truth for what "Implement" covers.

## 4. Implement only the approved scope

Implement exactly what was approved. Do not silently expand into adjacent roadmap items, refactors,
cleanup, or unrelated improvements. If something discovered during implementation means the
approved scope should change, stop and ask rather than continuing on your own judgment.

## 5. Verify

Validate the implementation — see `docs/procedures/validation.md` for ordering. Do not claim
success without evidence.

## 6. Stop for human acceptance

State plainly that implementation and verification are complete, reporting the verification status
(see `docs/procedures/completion.md`), and stop there. Do not commit and do not start another task
automatically. This project has no separate stop-token convention beyond stating completion clearly
— do not invent one.

If the user does not accept the work, treat that as new input, not a failed verification: return to
step 2 (Propose) with the rejection as context, rather than starting over from scratch.

## 7. Commit only after a separate, explicit commit request

Approval of the implementation is not approval to commit. Follow `AGENTS.md` — Git for commit and
push rules.

Keep `.agent/current-task.md` focused on the active task. Do not turn it into a project history.
