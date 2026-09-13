# Project Agent Instructions

## Project Context

This repository is an agent-managed software project.

Before making changes, inspect:
1. The relevant source code and tests.
2. `.agent/state.md` for current project state.
3. `.agent/current-task.md` when a current task exists.
4. Relevant files under `docs/` when requirements, architecture, or decisions matter.

Do not read every project document by default. Read only the documentation relevant to the current task.

## Source of Truth

Use the following hierarchy:

1. User instructions in the current task.
2. This `AGENTS.md` and applicable nested agent instructions.
3. `docs/requirements.md` for product requirements.
4. `docs/architecture.md` for system architecture.
5. `docs/decisions.md` for accepted architectural decisions.
6. `.agent/current-task.md` for the active task.
7. `.agent/state.md` for current project state.
8. Source code and tests for the implemented behavior.

If these sources conflict, stop and identify the conflict rather than silently choosing one.

## Requirements

- Reference requirements by their requirement ID when available.
- Do not invent requirements.
- Do not silently expand scope.
- When implementation changes the behavior described by a requirement, update the relevant documentation when appropriate.

## Architecture

- Follow the documented architecture.
- Do not introduce a new architectural pattern when an existing project pattern solves the problem.
- If a significant architectural decision is required, document the decision before or alongside the implementation.

## Task Execution

For non-trivial work:

1. Understand the task.
2. Inspect the relevant code and documentation.
3. State the intended approach.
4. Implement the smallest correct change.
5. Validate the change.
6. Review the diff.
7. Update project state/documentation when the durable project knowledge changed.

## Documentation

Keep documentation concise and useful.

Do not create:
- activity diaries
- per-command logs
- redundant summaries
- duplicate copies of requirements
- large progress histories

Record durable knowledge, decisions, requirements, and current state only.

## Completion

A task is not complete merely because code was changed.

Before reporting completion:
- Verify the implementation.
- Run relevant validation.
- Review the diff.
- Update `.agent/state.md` if project state changed.
- Identify any remaining concerns.

## Context Efficiency

- Do not read the entire repository unless the task genuinely requires it.
- Search for relevant files before reading large amounts of source code.
- Read only documentation relevant to the current task.
- Treat `.agent/state.md` as a concise current-state checkpoint, not a history log.
- Treat `.agent/current-task.md` as the single active task definition.
- Use Git history when historical implementation context is required.
- Do not create progress diaries or duplicate project documentation.
- Keep agent-facing documentation concise and authoritative.

## Definition of Done

For a non-trivial task, consider the task complete only when:

- The requested behavior is implemented.
- Relevant acceptance criteria are satisfied.
- Relevant tests are added or updated when appropriate.
- Relevant validation passes.
- The final diff has been reviewed.
- Required project documentation is updated when durable knowledge changed.
- `.agent/state.md` reflects the new project state when appropriate.

If a validation or completion step does not apply, state that explicitly rather than claiming it was performed.

## Requirement Traceability

- Reference requirement IDs when implementing requirements.
- A task should identify the requirements it addresses.
- Acceptance criteria should be testable whenever practical.
- Tests provide evidence for behavior; documentation defines intent.
- Do not invent requirements or acceptance criteria.

## Definition of Done

For a non-trivial task, consider the task complete only when:

- The requested behavior is implemented.
- Relevant acceptance criteria are satisfied.
- Relevant tests are added or updated when appropriate.
- Relevant validation passes.
- The final diff has been reviewed.
- Required project documentation is updated when durable knowledge changed.
- `.agent/state.md` reflects the new project state when appropriate.

If a validation or completion step does not apply, state that explicitly rather than claiming it was performed.

## Requirement Traceability

- Reference requirement IDs when implementing requirements.
- A task should identify the requirements it addresses.
- Acceptance criteria should be testable whenever practical.
- Tests provide evidence for behavior; documentation defines intent.
- Do not invent requirements or acceptance criteria.
