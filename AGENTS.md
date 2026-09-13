# Project Agent Instructions

## Project Context

This repository is an agent-managed software project.

Before making changes:

1. Inspect the relevant source code and tests.
2. Read `.agent/state.md` for the current project state.
3. Read `.agent/current-task.md` when an active task exists.
4. Read relevant files under `docs/` when requirements, architecture, decisions, or development procedures matter.
5. Inspect applicable nested `AGENTS.md` files when working in a subdirectory.

Do not read the entire repository or every project document by default. Read only what is relevant to the current task.

## Source of Truth

Use the following hierarchy:

1. Explicit user instructions in the current conversation.
2. This `AGENTS.md` and applicable nested agent instructions.
3. `docs/requirements.md` for product and functional requirements.
4. `docs/architecture.md` for system architecture.
5. `docs/decisions.md` for accepted architectural decisions.
6. `.agent/current-task.md` for the active task definition.
7. `.agent/state.md` for the current durable project state.
8. Source code and tests for implemented behavior.

If authoritative sources conflict, stop and identify the conflict rather than silently choosing one.

## Operating Principles

- Inspect before changing.
- Understand the existing architecture and conventions before modifying code.
- Make the smallest correct change.
- Preserve existing behavior unless the task explicitly requires changing it.
- Do not modify unrelated files.
- Prefer existing project patterns and tooling over introducing new ones.
- Stay within the requested project scope.
- Do not invent requirements, behavior, or acceptance criteria.

## Requirements

- Reference requirement IDs when available.
- Do not invent requirements.
- Do not silently expand scope.
- Identify the requirements addressed by non-trivial tasks.
- Keep acceptance criteria testable whenever practical.
- When implementation changes behavior described by a requirement, update the relevant documentation when appropriate.

## Architecture

- Follow the documented architecture.
- Inspect existing patterns before introducing new ones.
- Do not introduce a new architectural pattern when an existing project pattern solves the problem.
- Keep implementation consistent with established project conventions.
- If a significant architectural decision is required, document the decision before or alongside the implementation.
- Record the rationale for significant decisions in `docs/decisions.md`.

## Task Execution

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

## Context Efficiency

- Do not read the entire repository unless the task genuinely requires it.
- Search for relevant files before reading large amounts of source code.
- Read only documentation relevant to the current task.
- Prefer deterministic tools such as `rg`, `fd`, `git`, `jq`, `yq`, and project test commands for deterministic queries.
- Keep agent-facing documentation concise.
- Avoid loading historical context unless it is relevant to the current task.
- Use Git history when historical implementation context is required.
- Treat `.agent/state.md` as a concise current-state checkpoint, not a history log.
- Treat `.agent/current-task.md` as the single active task definition.
- Do not create activity diaries, per-command logs, or duplicate project documentation.
- Keep stable project instructions in `AGENTS.md`; keep dynamic project state in `.agent/state.md`.

## Dependencies

- Do not add, remove, or upgrade dependencies unless necessary for the requested work.
- When a dependency change is necessary, explain why and minimize the change.
- Prefer existing project dependencies and tooling.
- Validate dependency changes using the project's appropriate package manager and checks.

## Validation

Validation should match the scope and risk of the change.

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

Do not launch browser tests for changes that cannot affect user-visible browser behavior unless there is another clear reason to do so.

## Documentation

Keep documentation concise, accurate, and useful.

Record durable project knowledge in the appropriate location:

- `docs/requirements.md` — requirements and acceptance expectations.
- `docs/architecture.md` — system structure and technical architecture.
- `docs/decisions.md` — significant architectural and technical decisions with rationale.
- `docs/development.md` — development, testing, and validation procedures.
- `docs/troubleshooting.md` — known problems and their solutions.
- `.agent/state.md` — concise current project state.
- `.agent/roadmap.md` — milestones and future priorities.
- `.agent/current-task.md` — active task information.

Do not create:

- Activity diaries.
- Per-command logs.
- Large progress histories.
- Redundant summaries.
- Duplicate copies of requirements.
- Documentation that merely repeats source code.

## Secrets and Security

- Never expose secrets, credentials, API keys, access tokens, private keys, or sensitive configuration.
- Do not commit secrets.
- Do not copy secrets into agent-facing documentation.
- Treat environment files and credential stores as sensitive.
- Do not weaken security controls to make a task easier.
- Ask for clarification when a requested change could materially affect security.

## Scope and Safety

- Stay within the requested workspace.
- Do not modify unrelated files.
- Do not use destructive commands unless necessary and explicitly approved.
- Avoid irreversible operations when a reversible approach exists.
- Ask for clarification when ambiguity could materially change the implementation.
- Do not rewrite history unless explicitly requested.

## Git

- Never commit unless explicitly requested.
- Never push unless explicitly requested.
- Never rewrite Git history unless explicitly requested.
- Review the final diff before reporting completion.
- Keep commits focused when commits are requested.
- Do not include unrelated changes in a requested commit.
- Check `git status` and relevant diffs before and after significant Git operations.

## Requirement Traceability

For non-trivial work:

- Identify the requirement IDs addressed by the task when requirement IDs exist.
- Connect implementation decisions to the relevant requirements.
- Make acceptance criteria testable whenever practical.
- Use tests as evidence of implemented behavior.
- Use documentation to define intended behavior.
- Do not invent requirements or acceptance criteria.
- If a requirement cannot be validated directly, explain the limitation.

## Completion

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

## Communication

Before substantial changes:

- Briefly state the intended approach.
- Identify important assumptions or constraints.

After changes:

- Summarize what changed.
- Identify files changed.
- Report validation actually performed.
- Report whether browser verification was required and performed.
- Identify remaining concerns or limitations.

Keep communication concise and factual.
