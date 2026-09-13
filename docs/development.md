# Development Workflow

## Overview

Projects should follow a small, explicit lifecycle:

1. Define the requirement.
2. Define or confirm the architecture.
3. Create the active task.
4. Implement the smallest correct change.
5. Validate the implementation.
6. Verify affected user-visible flows when applicable.
7. Review the final diff.
8. Update durable project state and documentation.
9. Commit when explicitly requested.

## Starting a Task

Before implementation:

- Read `.agent/state.md`.
- Read `.agent/current-task.md` when an active task exists.
- Read the relevant requirements.
- Read relevant architecture and decision documentation.
- Inspect the affected source code and tests.
- Identify applicable constraints.

For a non-trivial task, populate `.agent/current-task.md` with:

- Objective
- Why
- Requirements
- Constraints
- Relevant Context
- Plan
- Validation
- Status

## Implementation

During implementation:

- Make the smallest correct change.
- Follow existing project patterns.
- Avoid unrelated refactoring.
- Do not add dependencies unless necessary.
- Keep the active task status accurate.
- Update the plan if the implementation approach materially changes.

## Validation

Use the smallest validation that provides meaningful evidence.

When applicable:

1. Formatter
2. Linter
3. Type checker
4. Targeted unit tests
5. Integration tests
6. Browser or end-to-end verification
7. Regression validation

Do not claim a check passed unless it was actually run.

## Browser Verification

When a change affects a user-visible browser flow:

- Use the project's pinned browser-testing tooling.
- Verify the affected flow.
- Reproduce failures before changing the implementation when practical.
- Inspect diagnostics when verification fails.
- Fix the underlying issue.
- Rerun the affected flow.
- Perform appropriate regression verification.

Browser verification is not required for changes that cannot affect user-visible browser behavior.

## Completion

Before declaring a non-trivial task complete:

- Confirm the requested behavior.
- Confirm relevant acceptance criteria.
- Run relevant validation.
- Review the final diff.
- Check for unintended changes.
- Update `.agent/state.md` when durable project state changed.
- Update relevant documentation when durable knowledge changed.
- Record remaining concerns or limitations.

## Git

Git operations are deliberate.

- Do not commit unless explicitly requested.
- Do not push unless explicitly requested.
- Do not rewrite history unless explicitly requested.
- Review the diff before committing.
- Keep commits focused and logically coherent.
- Do not include unrelated changes.

## Documentation Updates

Update documentation when implementation changes durable project knowledge.

Use:

- `docs/requirements.md` for requirements.
- `docs/architecture.md` for architecture.
- `docs/decisions.md` for significant decisions and rationale.
- `docs/development.md` for development workflow.
- `docs/troubleshooting.md` for known problems and solutions.
- `.agent/state.md` for current durable state.
- `.agent/roadmap.md` for milestones and priorities.

Do not create activity logs or duplicate documentation.

## Task Completion Record

After completing a task, update `.agent/current-task.md` so that it accurately reflects:

- What was accomplished.
- Which requirements were addressed.
- What validation was performed.
- The final status.

Then update `.agent/state.md` if the project's durable state changed.
