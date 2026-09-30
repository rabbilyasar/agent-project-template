#!/usr/bin/env python3
"""Stage 9 (Claude variant): the real Claude (Anthropic Messages API) evaluation run.

    load corpus -> leakage preflight -> deterministic DP-22 prefilter
    -> select eligible System-1 rows -> existing model_facing_input
    -> Claude adapter -> canonical results -> existing scorer/calibration/aggregation
    -> serialized evaluation artifact

Structurally identical to 09_run_evaluation_deepseek.py (same pipeline, same guardrails,
same DP-22 handling, same aggregation shape), duplicated as a separate entry-point script
rather than generalized into a shared multi-provider runner, for the same reason that file
gives for not merging with 09_run_evaluation.py: different providers, different wire
formats and auth, and the existing files are already-approved and untouched. Every shared
pipeline module (01, 02, 04, 06, 07, 08, adapter_base) is imported and used exactly as
already implemented; none are modified. claude_adapter.py itself is also used completely
unmodified.

Requires ANTHROPIC_API_KEY and ANTHROPIC_WORKSPACE_ID in this process's own environment
(read once, at call time, inside the injected transport function -- never printed, never
written to any file).

Phase 4.6: rows with inclusion_status=exclude are never sent to Claude (their IDs are
listed in the manifest), and the run aborts before any request unless the planned call set
is exactly EXPECTED_CLAUDE_CALLS rows and the evaluation inputs are committed. The manifest
records the harness commit and the SHA-256 of every prompt contract. `--plan-only` runs the
preflight and prints the planned calls without making any request.

Never writes into laya/corpus/. Writes run manifest + predictions + per-decision-type
aggregate reports under laya/results/<run_id>/.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = LIB_DIR.parents[0] / "prompts"
RESULTS_DIR = LIB_DIR.parents[1] / "results"
REPO_DIR = LIB_DIR.parents[2]

sys.path.insert(0, str(LIB_DIR))
from _module_loader import load_lib_module  # noqa: E402

load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")
preflight_mod = load_lib_module("02_leakage_preflight.py", "leakage_preflight")
prefilter_mod = load_lib_module("04_deterministic_prefilter.py", "prefilter")
aggregate_mod = load_lib_module("07_aggregate_report.py", "aggregate")
serialize_mod = load_lib_module("08_serialize_result.py", "serialize")
import claude_adapter  # noqa: E402
from adapter_base import build_canonical_result  # noqa: E402

RESULT_SCHEMA_VERSION = "1.0"
DP22_TYPE = "agent_verification_applicable"
NON_DP22_TYPES = ["trivial_vs_staged", "documented_limitation_vs_defect", "human_acceptance_required"]
EXPECTED_CORPUS_HASH = "a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b"
EXPECTED_DP22_SYSTEM1_IDS = {"ZEUS-DP22-02", "ZEUS-DP22-03"}
# Phase 4.6: excluded corpus rows are never sent to Claude (they are never scored either).
EXPECTED_SKIPPED_EXCLUDED_IDS = {"AGENT-DP11-01", "JOSS-DP11-01", "ZEUS-DP16-02"}
EXPECTED_CLAUDE_CALLS = 26
PROVENANCE_PATHS = ["laya/harness", "laya/corpus", "laya/schema", "laya/validate_corpus.py"]

CLAUDE_MODEL = claude_adapter.DEFAULT_MODEL
CLAUDE_MAX_TOKENS = claude_adapter.DEFAULT_MAX_TOKENS
ANTHROPIC_VERSION = claude_adapter.ANTHROPIC_VERSION
ANTHROPIC_ENDPOINT = claude_adapter.ANTHROPIC_ENDPOINT


def _load_allowed_values(decision_type: str) -> list[str]:
    contract = json.loads((PROMPTS_DIR / f"{decision_type}.json").read_text(encoding="utf-8"))
    return contract["allowed_output_values"]


def _real_transport(request_body: dict) -> dict:
    """Reads ANTHROPIC_API_KEY / ANTHROPIC_WORKSPACE_ID at call time -- never at import
    time, never cached, never printed. Raises on any transport/HTTP failure;
    claude_adapter.ClaudeAdapter.predict() is what converts that into an error
    PredictionEnvelope -- this function itself never retries and never rescues a failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not present in this process's environment")
    workspace_id = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if not workspace_id:
        raise RuntimeError("ANTHROPIC_WORKSPACE_ID not present in this process's environment")
    data = json.dumps(request_body).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_ENDPOINT, data=data, method="POST",
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-workspace-id": workspace_id,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body[:500]}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"network error: {e.reason}") from None
    parsed = json.loads(body)
    parsed["_http_status"] = status
    return parsed


def _provenance() -> dict:
    """Git commit + clean/dirty state of the evaluation inputs, and a hash of each prompt
    contract (the contracts carry no version field of their own)."""
    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(REPO_DIR), *args], capture_output=True, text=True, check=True).stdout.strip()
    return {
        "harness_git_commit": git("rev-parse", "HEAD"),
        "harness_uncommitted_changes": bool(git("status", "--porcelain", "--", *PROVENANCE_PATHS)),
        "prompt_contract_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PROMPTS_DIR.glob("*.json"))
        },
    }


def preflight() -> dict:
    """All checks required before any real request: corpus hash, model identifier,
    configuration, decision counts, deterministic-prefilter status, credential presence
    (never its value). Aborts (raises SystemExit) rather than proceeding on any mismatch --
    never regenerates or "fixes" the corpus."""
    rows, corpus_hash = load_corpus_mod.load_corpus()
    if corpus_hash != EXPECTED_CORPUS_HASH:
        raise SystemExit(f"ABORT: corpus_content_hash mismatch. expected={EXPECTED_CORPUS_HASH} actual={corpus_hash}")
    if len(rows) != 36:
        raise SystemExit(f"ABORT: expected 36 corpus rows, loaded {len(rows)}")

    counts: dict[str, int] = {}
    for r in rows:
        counts[r.decision_type] = counts.get(r.decision_type, 0) + 1
    expected_counts = {
        "trivial_vs_staged": 7, "agent_verification_applicable": 9,
        "documented_limitation_vs_defect": 8, "human_acceptance_required": 12,
    }
    if counts != expected_counts:
        raise SystemExit(f"ABORT: decision-type counts mismatch. expected={expected_counts} actual={counts}")

    dp22_rows = [r for r in rows if r.decision_type == DP22_TYPE]
    dp22_system1_ids = set()
    for row in dp22_rows:
        prefilter_out = prefilter_mod.deterministic_prefilter(row.decision_type, load_corpus_mod.model_facing_payload(row))
        partition = row.raw.get("corpus_partition")
        if not prefilter_out["handled"] and partition == "system1_judgment":
            dp22_system1_ids.add(row.candidate_id)
    if dp22_system1_ids != EXPECTED_DP22_SYSTEM1_IDS:
        raise SystemExit(f"ABORT: DP-22 System-1 row set mismatch. expected={EXPECTED_DP22_SYSTEM1_IDS} actual={dp22_system1_ids}")

    planned_ids = sorted(dp22_system1_ids) + [
        r.candidate_id for r in rows
        if r.decision_type in NON_DP22_TYPES and r.raw["inclusion_status"] != "exclude"
    ]
    skipped_excluded_ids = sorted(
        r.candidate_id for r in rows
        if r.decision_type in NON_DP22_TYPES and r.raw["inclusion_status"] == "exclude"
    )
    if set(skipped_excluded_ids) != EXPECTED_SKIPPED_EXCLUDED_IDS:
        raise SystemExit(f"ABORT: skipped excluded row set mismatch. expected={sorted(EXPECTED_SKIPPED_EXCLUDED_IDS)} actual={skipped_excluded_ids}")
    if len(planned_ids) != EXPECTED_CLAUDE_CALLS or len(set(planned_ids)) != len(planned_ids):
        raise SystemExit(f"ABORT: expected {EXPECTED_CLAUDE_CALLS} distinct Claude calls, planned {len(planned_ids)}")

    provenance = _provenance()
    if provenance["harness_uncommitted_changes"]:
        raise SystemExit(f"ABORT: uncommitted changes under {PROVENANCE_PATHS}; commit before a paid run")

    model_identifier = claude_adapter.build_model_identifier(CLAUDE_MODEL)
    if model_identifier != "claude:claude-haiku-4-5-20251001:direct-api":
        raise SystemExit(f"ABORT: model_identifier does not match the required literal: {model_identifier!r}")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ABORT: ANTHROPIC_API_KEY not present in this process's environment")
    if not os.environ.get("ANTHROPIC_WORKSPACE_ID"):
        raise SystemExit("ABORT: ANTHROPIC_WORKSPACE_ID not present in this process's environment")

    report = {
        "corpus_content_hash": corpus_hash,
        "corpus_hash_matches_expected": True,
        "decision_counts": counts,
        "model_identifier": model_identifier,
        "model_configuration": {"model": CLAUDE_MODEL, "max_tokens": CLAUDE_MAX_TOKENS, "anthropic_version": ANTHROPIC_VERSION},
        "dp22_system1_row_ids": sorted(dp22_system1_ids),
        "planned_claude_call_count": len(planned_ids),
        "planned_claude_candidate_ids": planned_ids,
        "skipped_excluded_candidate_ids": skipped_excluded_ids,
        **provenance,
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "api_credential_present": True,
        "workspace_id_present": True,
    }
    print("=== PREFLIGHT ===")
    print(json.dumps(report, indent=2))
    print()
    return report


def run(plan_only: bool = False) -> dict:
    pf = preflight()
    if plan_only:
        return {"preflight": pf}
    run_id = f"phase4.6-claude-{CLAUDE_MODEL}-real-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    corpus_hash = pf["corpus_content_hash"]
    model_identifier = pf["model_identifier"]

    rows, _ = load_corpus_mod.load_corpus()
    corpus_rows_by_id = {r.candidate_id: r.raw for r in rows}

    # --- leakage preflight, every row, before any model call ---
    for row in rows:
        rendered = str(load_corpus_mod.model_facing_payload(row))
        result = preflight_mod.check_leakage(rendered, row.raw)
        if not result.passed:
            raise SystemExit(f"ABORT: leakage preflight failed for {row.candidate_id}: {result.hard_failures}")

    adapter = claude_adapter.ClaudeAdapter(
        transport=_real_transport, model=CLAUDE_MODEL, max_tokens=CLAUDE_MAX_TOKENS,
    )

    manifest = {
        "run_id": run_id,
        "corpus_content_hash": corpus_hash,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "provider": "claude",
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "anthropic_version": ANTHROPIC_VERSION,
        "model_identifier": model_identifier,
        "harness_git_commit": pf["harness_git_commit"],
        "harness_uncommitted_changes": pf["harness_uncommitted_changes"],
        "prompt_contract_sha256": pf["prompt_contract_sha256"],
        "planned_claude_call_count": pf["planned_claude_call_count"],
        "skipped_excluded_candidate_ids": pf["skipped_excluded_candidate_ids"],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    all_results: list[dict] = []

    # --- DP-22: deterministic prefilter first; only system1_judgment rows go to Claude ---
    dp22_rows = [r for r in rows if r.decision_type == DP22_TYPE]
    dp22_allowed = _load_allowed_values(DP22_TYPE)
    dp22_claude_rows = []
    for row in dp22_rows:
        prefilter_out = prefilter_mod.deterministic_prefilter(row.decision_type, load_corpus_mod.model_facing_payload(row))
        partition = row.raw.get("corpus_partition")
        if not prefilter_out["handled"] and partition == "system1_judgment":
            dp22_claude_rows.append(row)
        else:
            all_results.append(prefilter_mod.build_canonical_result(
                row.candidate_id, row.decision_type, run_id, corpus_hash, dp22_allowed, prefilter_out,
            ))

    if {r.candidate_id for r in dp22_claude_rows} != EXPECTED_DP22_SYSTEM1_IDS:
        raise SystemExit(f"ABORT: expected exactly {EXPECTED_DP22_SYSTEM1_IDS}, got {[r.candidate_id for r in dp22_claude_rows]}")

    def _run_claude_group(group_rows, decision_type):
        allowed = _load_allowed_values(decision_type)
        results = []
        for row in group_rows:
            state = load_corpus_mod.model_facing_payload(row)
            # One request per row, no retry, no rescue on failure -- claude_adapter's own
            # predict() already converts any transport/API/parse failure into an error
            # PredictionEnvelope rather than raising.
            envelope = adapter.predict(decision_type, state, allowed)
            results.append(build_canonical_result(row.candidate_id, decision_type, run_id, corpus_hash, envelope))
            status = "OK" if envelope.valid_prediction else f"FAIL ({envelope.error})"
            print(f"  {row.candidate_id}: {status}")
        return results

    to_call_ids = [r.candidate_id for r in dp22_claude_rows] + [
        r.candidate_id for r in rows
        if r.decision_type in NON_DP22_TYPES and r.raw["inclusion_status"] != "exclude"
    ]
    if sorted(to_call_ids) != sorted(pf["planned_claude_candidate_ids"]):
        raise SystemExit("ABORT: rows about to be sent to Claude differ from the preflight plan")

    print(f"=== DP-22 system1_judgment ({len(dp22_claude_rows)} rows) ===")
    all_results.extend(_run_claude_group(dp22_claude_rows, DP22_TYPE))

    for decision_type in NON_DP22_TYPES:
        group_rows = [r for r in rows if r.decision_type == decision_type and r.raw["inclusion_status"] != "exclude"]
        print(f"=== {decision_type} ({len(group_rows)} rows) ===")
        all_results.extend(_run_claude_group(group_rows, decision_type))

    expected_results = len(rows) - len(pf["skipped_excluded_candidate_ids"])
    if len(all_results) != expected_results:
        raise SystemExit(f"ABORT: expected {expected_results} canonical results, produced {len(all_results)}")

    # --- serialize predictions (never into laya/corpus/) ---
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    serialize_mod.write_results_jsonl(all_results, run_dir / "predictions.jsonl")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # --- score + aggregate, per decision type (identical structure to the Laya/DeepSeek runs) ---
    results_by_type: dict[str, list[dict]] = {}
    for r in all_results:
        results_by_type.setdefault(r["decision_type"], []).append(r)

    reports: dict[str, dict] = {}

    reports["trivial_vs_staged"] = aggregate_mod.build_report(
        "trivial_vs_staged", results_by_type.get("trivial_vs_staged", []), corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    dp16_scoring_eligible = [
        r for r in results_by_type.get("documented_limitation_vs_defect", [])
        if corpus_rows_by_id[r["candidate_id"]]["inclusion_status"] != "exclude"
    ]
    reports["documented_limitation_vs_defect"] = aggregate_mod.build_report(
        "documented_limitation_vs_defect", dp16_scoring_eligible, corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    dp23_scoring_eligible = [
        r for r in results_by_type.get("human_acceptance_required", [])
        if corpus_rows_by_id[r["candidate_id"]]["inclusion_status"] != "exclude"
    ]
    reports["human_acceptance_required"] = aggregate_mod.build_report(
        "human_acceptance_required", dp23_scoring_eligible, corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    dp22_results = results_by_type.get(DP22_TYPE, [])
    deterministic_dp22 = [r for r in dp22_results if r["model_identifier"] == prefilter_mod.MODEL_IDENTIFIER]
    claude_dp22 = [r for r in dp22_results if r["model_identifier"] == model_identifier]
    det_report = aggregate_mod.build_report(
        DP22_TYPE, deterministic_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, prefilter_mod.MODEL_IDENTIFIER,
    )
    claude_report = aggregate_mod.build_report(
        DP22_TYPE, claude_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, model_identifier,
    )
    reports[DP22_TYPE] = {
        "run_id": run_id, "corpus_content_hash": corpus_hash, "schema_version": RESULT_SCHEMA_VERSION,
        "decision_type": DP22_TYPE, "model_identifier": "mixed (see per-block model_identifier)",
        "blocks": {**det_report["blocks"], **claude_report["blocks"]},
    }

    (run_dir / "aggregate_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nWrote: {run_dir}/predictions.jsonl ({len(all_results)} rows)")
    print(f"Wrote: {run_dir}/aggregate_report.json")
    print(f"Wrote: {run_dir}/manifest.json")

    return {"run_id": run_id, "run_dir": str(run_dir), "manifest": manifest, "reports": reports, "results": all_results}


if __name__ == "__main__":
    run(plan_only="--plan-only" in sys.argv[1:])
