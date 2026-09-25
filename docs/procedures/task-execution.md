# Task Execution

This procedure defines how to carry out non-trivial work. It is operational reference (see
`AGENTS.md` — Source of Truth): consult it for how to execute a task, not for what to build.

## Process

For non-trivial work:

1. Understand the objective and requirements.
2. Inspect the relevant code, tests, and documentation.
3. Identify constraints and applicable architectural decisions.
4. State the intended approach before substantial changes.
5. Implement the smallest correct change.
6. Run the smallest relevant validation.
7. Run broader validation when appropriate.
8. Verify affected user-visible flows when applicable.
9. Review the final diff.
10. Update durable project state or documentation when it changed.

Keep `.agent/current-task.md` focused on the active task. Do not turn it into a project history.
