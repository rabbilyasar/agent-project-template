# Benchmark harness

Pipeline stages live one-per-file under `lib/`, numbered in execution order so the sequence is
self-documenting and `run_benchmark.sh` is a plain top-to-bottom script, not a router or dynamic
dispatcher:

1. `01_fixture_prepare.sh` — copy `bench/fixture` at a pinned commit into a fresh scratch
   directory. No git, no template, no agent involvement.
2. `02_stamp_template.sh` — install the requested arm's template (`v1` = commit `c0ba3a7`, `v2` =
   the current working tree) into the scratch directory via the *existing, already-tested*
   `bin/agent-init-install` + `bin/agent-init` pipeline. No new stamping logic is introduced; this
   only wraps the tool that already exists.
3. `03_trial_isolate.sh` — turn the stamped scratch directory into a realistic, isolated trial: git
   init, initial commit, a local bare `origin` remote, and (for safety scenarios) whatever
   scenario-specific pre-state a task's setup calls for. Also prepares a stripped Claude Code
   config directory containing no personal plugins/skills/hooks.
4. `04_invoke_claude.sh` — the only stage that would call the `claude` CLI. **Not invoked by
   anything in this repository yet.** `run_benchmark.sh` calls it only when
   `BENCH_ALLOW_CLAUDE_INVOKE=1` is set, so no accidental run can happen while this is still
   infrastructure.
5. `05_collect_transcript.py` — parse the raw `--output-format json` transcript into token counts
   (input/output/cache-read/cache-write), tool-call counts by name, distinct files read/modified,
   wall time, and human-intervention count (AskUserQuestion / plan-approval events).
6. `06_validate.sh` — copy the task's hidden validation assets from `harness/hidden_tests/<task>/`
   into the trial directory (the agent never saw them during the trial) and independently re-run
   the fixture's real formatter/linter/type-checker/tests/e2e plus any task-specific hidden test.
   Never trusts the agent's own claim that validation passed.
7. `07_safety_detect.py` — for safety-class tasks, scan the recorded tool-call log and a
   before/after git diff for the specific violation pattern that task defines.
8. `08_serialize_result.py` — combine metadata + the outputs of stages 5–7 into one JSON line
   matching `schema/result_schema.json`, appended to `bench/results/results.jsonl` (or
   `safety_results.jsonl` for safety tasks). No dollar amount is computed here; pricing is
   supplied separately at analysis time (`schema/pricing.example.json` shows the shape).

`tests/` holds self-tests for this infrastructure only — they never invoke Claude Code. They check
that task definitions are complete, that stages 1–2 actually produce a working v1 and v2 trial
directory from the real template, and that the parsers in stages 5 and 7 behave correctly against
small synthetic transcripts authored by hand.

`hidden_tests/` holds the validation assets referenced by `06_validate.sh` — regression/acceptance
tests the agent must not see during a trial. Keeping them outside `bench/fixture/` is what makes
them hidden.

## Isolation from the operator's own Claude Code configuration

This benchmark measures the `AGENTS.md`/`docs/procedures/`/`.claude/skills/` architecture, not
whatever personal plugins, skills, or hooks happen to be active in an interactive session. This
matters concretely: the operator machine this was developed on has `ponytail`, `superpowers`,
`frontend-design`, and `playwright` enabled via `enabledPlugins` in the **user**-scope
`~/.claude/settings.json`, plus unrelated `atuin` shell-history hooks in the same file — none of
which are part of the template under test, and all of which must not reach a trial.

### Mechanism (verified, not assumed)

Each trial runs with:

```
CLAUDE_CONFIG_DIR=<fresh, never-reused dir> \
  claude --setting-sources project --permission-mode bypassPermissions \
         --output-format json -p "<prompt>"
```

executed with the process's working directory set to the trial directory (see
`lib/04_invoke_claude.sh`, gated off until `BENCH_ALLOW_CLAUDE_INVOKE=1`).

- **`CLAUDE_CONFIG_DIR`** redirects Claude Code's entire user-level state tree — settings.json,
  installed plugins, credentials, session history, and built-in auto-memory — away from the
  operator's real `~/.claude`. **Verified empirically** against the installed CLI (`claude
  --version` → `2.1.282`, commit `88e628ac8735`, 2026-09-25): `claude doctor` under the operator's
  real config reports a resolved org policy and credentials; the identical command with
  `CLAUDE_CONFIG_DIR` pointed at a fresh empty directory reports no credentials and no org policy —
  a fresh, contamination-free state. This variable is real and load-bearing on this version, but it
  is **not documented** in the official CLI reference (confirmed by searching
  `code.claude.com/docs`), so it is a checked assumption about the *current* installed version, not
  a stable public contract — see Remaining risks below.
- **`--setting-sources project`** is the officially documented complement (`code.claude.com/docs/en/settings`):
  it restricts which settings scopes load to `project` only, explicitly excluding `user` and
  `local`. Belt-and-suspenders alongside `CLAUDE_CONFIG_DIR` — if the fresh config directory ever
  unexpectedly picked up a settings.json, plugin-derived settings still could not apply.
- A fresh, unique `CLAUDE_CONFIG_DIR` per trial (created by `lib/03_trial_isolate.sh`, never reused)
  is what gives "no context from previous Claude sessions": there is no session-history file to
  resume from and no prior auto-memory for any project path, because the whole tree is new.

### Why not `--bare` or `--safe-mode`

Both were considered and rejected after checking their actual documented/reported behavior, not
their names:

- **`--safe-mode`** disables *all* customizations including project skills — it would disable
  `.claude/skills/` itself, breaking the exact mechanism V2 is being measured on.
- **`--bare`** also disables CLAUDE.md auto-discovery, and — more importantly — clamps the
  available tool set to `["Bash", "Edit", "Read"]`, **removing the `Skill` tool entirely**
  (confirmed via `claude --help`'s own description and a reported/reproduced upstream issue,
  anthropics/claude-code#84633). Under `--bare`, V2's skills could be named in a slash command but
  the model would have no tool to invoke one — this would silently make V2 behave like a
  no-skills baseline, invalidating the comparison. The same issue thread's own suggested
  workaround for real isolation is exactly the `CLAUDE_CONFIG_DIR` approach used here.

### Known consequences to account for when interpreting results

- **Permissions are bypassed** (`--permission-mode bypassPermissions`), because headless execution
  has no human to answer a permission prompt. This means the safety suite
  (`bench/tasks/safety/`) tests the *model's own judgment* — does it choose to ask via
  `AskUserQuestion` or refuse — not whether Claude Code's permission system blocks a dangerous
  command. Do not read a safety pass as "the permission system caught it."
- **Auth**: a fresh `CLAUDE_CONFIG_DIR` has no credentials file, so OAuth/keychain login (which
  lives under the operator's real `~/.claude`) does not work. `ANTHROPIC_API_KEY` (or an
  `apiKeyHelper` supplied via `--settings`) must be set before a real trial can run — this is a
  prerequisite for whoever runs the benchmark, not something the harness can supply.
- **Org-managed policy settings**, if the execution machine has any, always load regardless of
  `--setting-sources` or `CLAUDE_CONFIG_DIR` (per the official settings-precedence docs). This is
  outside the harness's control and is the same for every trial in both arms, so it does not bias
  V1 vs. V2 relative to each other, but it means "fully clean" is not literally achievable on a
  managed machine.
