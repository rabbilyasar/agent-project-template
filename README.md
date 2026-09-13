# Agent Project Template

A minimal, vendor-neutral scaffold for software projects built with AI coding agents — Claude Code, Codex
CLI, or anything else that reads an `AGENTS.md`. It provides stable agent instructions, a place for
concise durable project state, durable project knowledge (requirements, architecture, decisions,
development commands, troubleshooting), and a small CLI tool that stamps all of it into a project
directory without cloning this repository.

This repository is itself a valid instance of the template: `AGENTS.md`, `CLAUDE.md`, `.agent/`, and
`docs/` at the root are the canonical source the tool installs and copies from.

## Design Principles

- **Stable instructions stay stable.** `AGENTS.md` rarely changes; it holds process and rules, not project
  facts.
- **Dynamic state stays concise.** `.agent/state.md` and `.agent/current-task.md` hold only what an agent
  needs right now. History belongs in Git, not in a growing state file.
- **Discover, don't dump.** Agents read what's relevant to the current task, not every document, every
  time.
- **Deterministic over improvised.** Prefer real tests, linters, and scripts over asking an agent to guess
  at something a tool could answer directly — starting with `docs/development.md` for this project's
  actual commands.
- **No vendor lock-in.** `AGENTS.md` is the single source of truth for agent instructions. Vendor-specific
  files such as `CLAUDE.md` only import it; they never duplicate or override it.

## Installing the Tool

From a clone of this repository, run once:

```
bin/agent-init-install
```

This installs:

- `agent-init` to `~/.local/bin/agent-init` (make sure that directory is on your `PATH`).
- A copy of the template files to `~/.local/share/agent-init`.

Re-run it any time — for example after pulling changes to this repository — to refresh both.

## Initializing a Project

```
agent-init /path/to/project
```

This creates the directory if it doesn't exist and copies the template into it:

- `AGENTS.md`, `CLAUDE.md` — agent instructions (`CLAUDE.md` just imports `AGENTS.md`).
- `README.md` — a starter README for the new project.
- `.agent/current-task.md`, `.agent/state.md`, `.agent/roadmap.md` — task, state, and roadmap tracking.
- `docs/requirements.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/development.md`,
  `docs/troubleshooting.md` — durable project knowledge.

`agent-init` never overwrites an existing file — it prints `SKIP` and leaves it alone. That makes it safe
to run against a project that already has some of these files in place, and safe to re-run after an
interrupted run (anything already created is left untouched; anything missing is filled in).

Every check that could fail runs before any file is written, so a missing or corrupted template, or a
destination path that collides with an existing file of the wrong type, is reported without leaving the
project partially initialized.

## What Gets Generated

A freshly initialized project intentionally contains no real requirements, decisions, architecture, or
progress. Every field is either literal placeholder text (`Not defined.`, `None defined.`) or an
HTML-comment instruction describing what belongs there. Replace placeholders with real content as the
project takes shape — don't leave them in place once the real answer is known, and don't mistake them for
actual project state.

## Updating the Template

Edit the files at the root of this repository (`AGENTS.md`, `CLAUDE.md`, `.agent/`, `docs/`,
`PROJECT_README.md`), then run `bin/agent-init-install` again to refresh the installed copy. Projects
that were already initialized are unaffected — copy over specific updated files by hand if you want an
existing project to pick up a template change.

## Repository Layout

- `AGENTS.md`, `CLAUDE.md`, `.agent/`, `docs/`, `PROJECT_README.md` — the template content itself.
- `bin/agent-init` — the initializer.
- `bin/agent-init-install` — installs the initializer and template for local use.
- `tests/test-agent-init.sh` — smoke tests for both.

## Testing

```
tests/test-agent-init.sh
```

Exercises the installer and initializer end to end in an isolated temporary `HOME` and project directory:
expected files, date substitution, idempotent re-runs, invalid arguments, and failure cases (missing or
empty template, destination path collisions).
