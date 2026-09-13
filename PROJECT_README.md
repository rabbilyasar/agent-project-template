# Project

## Purpose

<!-- What problem does this project solve? -->

Not defined.

## Status

<!-- Current high-level status. -->

Not started.

## Quick Start

<!-- Project-specific setup and development commands. -->

See `docs/development.md`.

## Project Workflow

This project uses the following workflow:

1. Define or update requirements.
2. Confirm the architecture and relevant decisions.
3. Define the active task in `.agent/current-task.md`.
4. Implement the smallest correct change.
5. Validate the implementation.
6. Verify affected user-visible flows when applicable.
7. Review the final diff.
8. Update durable project state and documentation.
9. Commit changes when appropriate.

## Agent Infrastructure

- `AGENTS.md` — Canonical agent operating instructions and project rules
- `CLAUDE.md` — Compatibility import so Claude Code also loads `AGENTS.md`
- `.agent/current-task.md` — Active task definition
- `.agent/state.md` — Current durable project state
- `.agent/roadmap.md` — Project milestones and priorities

## Documentation

- `docs/requirements.md` — Product and functional requirements
- `docs/architecture.md` — System architecture
- `docs/decisions.md` — Architectural and technical decisions
- `docs/development.md` — Setup, run, lint, test, and validation commands for this project
- `docs/troubleshooting.md` — Known problems and solutions

## Development

<!-- Project-specific development instructions. -->

See `docs/development.md`.

## Validation

<!-- Project-specific validation commands. -->

See `docs/development.md`.

## Git

Git commits and pushes are deliberate operations.

Never commit unless explicitly requested. Never push unless explicitly requested.
