#!/usr/bin/env bash
# Smoke tests for bin/agent-init and bin/agent-init-install.
# Dependency-free: plain bash + coreutils. Run from anywhere:
#   tests/test-agent-init.sh
set -euo pipefail

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

fail=0

pass() { printf 'PASS  %s\n' "$1"; }
fail_() { printf 'FAIL  %s\n' "$1"; fail=1; }

assert_success() {
    local desc=$1; shift
    if "$@" >/dev/null 2>&1; then pass "$desc"; else fail_ "$desc"; fi
}

assert_exit_code() {
    local desc=$1 expected=$2; shift 2
    local actual=0
    "$@" >/dev/null 2>&1 || actual=$?
    if [[ "$actual" -eq "$expected" ]]; then
        pass "$desc"
    else
        fail_ "$desc (expected exit $expected, got $actual)"
    fi
}

assert_file() {
    local desc=$1 path=$2
    if [[ -f "$path" ]]; then pass "$desc"; else fail_ "$desc ($path missing)"; fi
}

assert_not_exists() {
    local desc=$1 path=$2
    if [[ ! -e "$path" ]]; then pass "$desc"; else fail_ "$desc ($path unexpectedly exists)"; fi
}

assert_contains() {
    local desc=$1 needle=$2 haystack=$3
    if grep -qF -- "$needle" "$haystack" 2>/dev/null; then
        pass "$desc"
    else
        fail_ "$desc (\"$needle\" not found in $haystack)"
    fi
}

assert_not_contains() {
    local desc=$1 needle=$2 haystack=$3
    if [[ -f "$haystack" ]] && ! grep -qF -- "$needle" "$haystack" 2>/dev/null; then
        pass "$desc"
    else
        fail_ "$desc (\"$needle\" unexpectedly found in $haystack)"
    fi
}

echo "== shell syntax =="
assert_success "agent-init parses"         bash -n "$repo_root/bin/agent-init"
assert_success "agent-init-install parses" bash -n "$repo_root/bin/agent-init-install"

echo "== agent-init-install =="
fake_home="$work/home"
mkdir -p "$fake_home"
assert_success "install runs cleanly" env HOME="$fake_home" "$repo_root/bin/agent-init-install"

assert_file "installs agent-init binary" "$fake_home/.local/bin/agent-init"
template_dir="$fake_home/.local/share/agent-init"
for f in AGENTS.md CLAUDE.md README.md .agent/current-task.md .agent/state.md .agent/roadmap.md \
         docs/requirements.md docs/architecture.md docs/decisions.md docs/development.md docs/troubleshooting.md; do
    assert_file "template installs $f" "$template_dir/$f"
done

echo "== agent-init-install: refresh on re-run =="
refresh_repo="$work/refresh-repo"
mkdir -p "$refresh_repo/bin"
cp "$repo_root/bin/agent-init" "$refresh_repo/bin/agent-init"
cp "$repo_root/bin/agent-init-install" "$refresh_repo/bin/agent-init-install"
chmod +x "$refresh_repo/bin/agent-init" "$refresh_repo/bin/agent-init-install"
cp "$repo_root/AGENTS.md" "$refresh_repo/AGENTS.md"
cp "$repo_root/CLAUDE.md" "$refresh_repo/CLAUDE.md"
cp "$repo_root/PROJECT_README.md" "$refresh_repo/PROJECT_README.md"
cp -r "$repo_root/.agent" "$refresh_repo/.agent"
cp -r "$repo_root/docs" "$refresh_repo/docs"

refresh_home="$work/refresh-home"
mkdir -p "$refresh_home"
assert_success "refresh: initial install runs cleanly" env HOME="$refresh_home" "$refresh_repo/bin/agent-init-install"

refresh_template_dir="$refresh_home/.local/share/agent-init"
refresh_marker="REFRESH-MARKER-$$"
printf '\n%s\n' "$refresh_marker" >> "$refresh_repo/AGENTS.md"

assert_success "refresh: second install runs cleanly" env HOME="$refresh_home" "$refresh_repo/bin/agent-init-install"
assert_contains "refresh: installed template picks up a changed source file" "$refresh_marker" "$refresh_template_dir/AGENTS.md"

echo "== agent-init-install: top-level destination collision must not partially refresh =="
collision_home="$work/install-collision-home"
mkdir -p "$collision_home"
assert_success "collision: initial install runs cleanly" env HOME="$collision_home" "$repo_root/bin/agent-init-install"

collision_bin="$collision_home/.local/bin/agent-init"
collision_template_dir="$collision_home/.local/share/agent-init"
before_bin_hash="$(md5sum "$collision_bin" || true)"

# Corrupt the installed template destination itself so it's the wrong type
# (a file where a directory belongs), forcing the install's own
# "mkdir -p ... $template_dir" to fail before any manifest entry is touched.
rm -rf "$collision_template_dir"
printf 'i am a file, not the template directory\n' > "$collision_template_dir"

assert_exit_code "collision: install fails when template destination is the wrong type" 1 \
    env HOME="$collision_home" "$repo_root/bin/agent-init-install"

if [[ -f "$collision_template_dir" && ! -d "$collision_template_dir" ]]; then
    pass "collision: corrupted template destination is not partially converted"
else
    fail_ "collision: corrupted template destination is not partially converted"
fi
assert_contains "collision: corrupted template destination content is unchanged" \
    "i am a file, not the template directory" "$collision_template_dir"

after_bin_hash="$(md5sum "$collision_bin" || true)"
if [[ "$before_bin_hash" == "$after_bin_hash" ]]; then
    pass "collision: previously installed agent-init binary is left unchanged"
else
    fail_ "collision: previously installed agent-init binary is left unchanged"
fi

echo "== agent-init-install: nested destination collision must not partially refresh =="
nested_home="$work/install-nested-collision-home"
mkdir -p "$nested_home"
assert_success "nested collision: initial install runs cleanly" env HOME="$nested_home" "$repo_root/bin/agent-init-install"

nested_bin="$nested_home/.local/bin/agent-init"
nested_template_dir="$nested_home/.local/share/agent-init"
before_nested_agents_hash="$(md5sum "$nested_template_dir/AGENTS.md" || true)"
before_nested_bin_hash="$(md5sum "$nested_bin" || true)"

# Corrupt a destination nested well inside the template tree (not the
# template directory itself) so it's the wrong type: a directory where a
# regular file belongs. Without a destination preflight, `install` would
# silently install *into* this directory instead of failing.
rm -f "$nested_template_dir/docs/architecture.md"
mkdir -p "$nested_template_dir/docs/architecture.md"

assert_exit_code "nested collision: install fails when a nested destination is the wrong type" 1 \
    env HOME="$nested_home" "$repo_root/bin/agent-init-install"

if [[ -d "$nested_template_dir/docs/architecture.md" && ! -f "$nested_template_dir/docs/architecture.md/architecture.md" ]]; then
    pass "nested collision: corrupted destination is rejected, not silently absorbed"
else
    fail_ "nested collision: corrupted destination is rejected, not silently absorbed"
fi

after_nested_agents_hash="$(md5sum "$nested_template_dir/AGENTS.md" || true)"
if [[ "$before_nested_agents_hash" == "$after_nested_agents_hash" ]]; then
    pass "nested collision: unrelated already-installed template files are left unchanged"
else
    fail_ "nested collision: unrelated already-installed template files are left unchanged"
fi

after_nested_bin_hash="$(md5sum "$nested_bin" || true)"
if [[ "$before_nested_bin_hash" == "$after_nested_bin_hash" ]]; then
    pass "nested collision: previously installed agent-init binary is left unchanged"
else
    fail_ "nested collision: previously installed agent-init binary is left unchanged"
fi

echo "== agent-init: fresh initialization =="
today="$(date +%Y-%m-%d)"
proj="$work/fresh-project"
assert_success "init runs cleanly" env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$proj"

for f in AGENTS.md CLAUDE.md README.md .agent/current-task.md .agent/state.md .agent/roadmap.md \
         docs/requirements.md docs/architecture.md docs/decisions.md docs/development.md docs/troubleshooting.md; do
    assert_file "generates $f" "$proj/$f"
done

assert_contains "CLAUDE.md imports AGENTS.md" "@AGENTS.md" "$proj/CLAUDE.md"
assert_contains "state.md substitutes today's date" "$today" "$proj/.agent/state.md"
assert_contains "roadmap.md substitutes today's date" "$today" "$proj/.agent/roadmap.md"
assert_not_contains "no leftover {{INIT_DATE}} token in state.md" "{{INIT_DATE}}" "$proj/.agent/state.md"
assert_not_contains "no leftover {{INIT_DATE}} token in roadmap.md" "{{INIT_DATE}}" "$proj/.agent/roadmap.md"
assert_contains "decisions.md keeps its literal date placeholder" "YYYY-MM-DD" "$proj/docs/decisions.md"

echo "== agent-init: idempotent re-run =="
before_hash="$(cat "$proj/.agent/state.md" | md5sum || true)"
out="$(env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$proj")"
if echo "$out" | grep -q '^SKIP' && ! echo "$out" | grep -q '^CREATE'; then
    pass "re-run skips every existing file"
else
    fail_ "re-run skips every existing file (got: $out)"
fi
after_hash="$(cat "$proj/.agent/state.md" | md5sum || true)"
if [[ "$before_hash" == "$after_hash" ]]; then
    pass "re-run leaves existing content unchanged"
else
    fail_ "re-run leaves existing content unchanged"
fi

echo "== agent-init: partial project (some files already present) =="
partial="$work/partial-project"
mkdir -p "$partial"
printf 'custom content\n' > "$partial/AGENTS.md"
assert_success "init tolerates a pre-existing file" env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$partial"
assert_contains "pre-existing file is not overwritten" "custom content" "$partial/AGENTS.md"
assert_file "missing files are still filled in" "$partial/docs/requirements.md"

echo "== agent-init: invalid arguments =="
assert_exit_code "no arguments -> exit 2"        2 "$repo_root/bin/agent-init"
assert_exit_code "unknown option -> exit 2"      2 env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" --bogus
assert_exit_code "too many arguments -> exit 2"  2 "$repo_root/bin/agent-init" a b
assert_exit_code "--help -> exit 0"              0 "$repo_root/bin/agent-init" --help

echo "== agent-init: failure cases must not partially write =="

missing_template="$work/no-such-template"
never_created="$work/should-not-exist"
assert_exit_code "missing template dir -> exit 1" 1 env AGENT_INIT_TEMPLATE_DIR="$missing_template" "$repo_root/bin/agent-init" "$never_created"
assert_not_exists "project dir not created when template is missing" "$never_created"

empty_template="$work/empty-template"
mkdir -p "$empty_template"
never_created2="$work/should-not-exist-2"
assert_exit_code "template missing AGENTS.md -> exit 1" 1 env AGENT_INIT_TEMPLATE_DIR="$empty_template" "$repo_root/bin/agent-init" "$never_created2"
assert_not_exists "project dir not created when template has no AGENTS.md" "$never_created2"

collision="$work/collision-project"
mkdir -p "$collision"
printf 'i am a file, not a directory\n' > "$collision/.agent"
assert_exit_code "destination type collision -> exit 1" 1 env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$collision"
assert_not_exists "no files written before the collision was hit" "$collision/AGENTS.md"

not_a_dir="$work/plain-file"
printf 'x\n' > "$not_a_dir"
assert_exit_code "project path exists as a file -> exit 1" 1 env AGENT_INIT_TEMPLATE_DIR="$template_dir" "$repo_root/bin/agent-init" "$not_a_dir"

echo
if [[ "$fail" -eq 0 ]]; then
    echo "All checks passed."
else
    echo "Some checks FAILED." >&2
fi
exit "$fail"
