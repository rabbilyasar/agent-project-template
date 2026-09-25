# Project Agent Instructions

## Vendor Neutrality

This file is the canonical, vendor-neutral source of agent instructions. It is not specific to any AI
provider or tool. A `CLAUDE.md` file, if present, only imports this file for Claude Code's benefit and
must never duplicate or diverge from it. Any other vendor-specific entry point must do the same: import,
don't fork.

## Project Context

This repository is an agent-managed software project.

Before making changes:

1. Inspect the relevant source code and tests.
2. Read `.agent/state.md` for the current project state.
3. Read `.agent/current-task.md` when an active task exists.
4. Read relevant files under `docs/` when requirements, architecture, decisions, or development commands matter.
5. Read the relevant file under `docs/procedures/` when task execution, validation, completion,
   traceability, debugging, or communication process matters.
6. Inspect applicable nested `AGENTS.md` files when working in a subdirectory.

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

`docs/development.md` (setup, run, lint, test, and validation commands), `docs/troubleshooting.md`
(known problems and solutions), and `docs/procedures/` (task execution, validation, completion,
traceability, and debugging process) are operational reference, not part of this conflict-resolution
hierarchy — consult them for how to do something, not for what to build.

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

## Process Procedures

Detailed, situational process guidance lives under `docs/procedures/` and is read on demand, not
inlined here:

- `docs/procedures/task-execution.md` — the staged investigate/propose/approve/implement/verify/accept process for non-trivial work.
- `docs/procedures/validation.md` — validation ordering and browser/end-to-end verification.
- `docs/procedures/requirement-traceability.md` — connecting work to requirement IDs.
- `docs/procedures/completion.md` — the Definition of Done checklist.
- `docs/procedures/debugging.md` — the reproduce, isolate, root-cause, fix, and verify lifecycle.
- `docs/procedures/communication.md` — what to report before and after changes.

Do not duplicate this content in `AGENTS.md`. A Claude Code skill under `.claude/skills/` may point
to one of these files to load it automatically at the right moment; it must not duplicate it either.
If a procedure needs to change, edit the file under `docs/procedures/`, not `AGENTS.md` or a skill.

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
- Keep the stable instruction kernel in `AGENTS.md`; keep detailed, situational process guidance in
  `docs/procedures/`, loaded only when it applies; keep dynamic project state in `.agent/state.md`.
- Read `docs/procedures/*.md` only when the current task calls for that specific process (task
  execution, validation, completion, traceability, debugging, communication) — not as standing
  context.

## Dependencies

- Do not add, remove, or upgrade dependencies unless necessary for the requested work.
- When a dependency change is necessary, explain why and minimize the change.
- Prefer existing project dependencies and tooling.
- Validate dependency changes using the project's appropriate package manager and checks.

## Documentation

Keep documentation concise, accurate, and useful.

Record durable project knowledge in the appropriate location:

- `docs/requirements.md` — requirements and acceptance expectations.
- `docs/architecture.md` — system structure and technical architecture.
- `docs/decisions.md` — significant architectural and technical decisions with rationale.
- `docs/development.md` — this project's actual setup, run, lint, test, and validation commands.
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
