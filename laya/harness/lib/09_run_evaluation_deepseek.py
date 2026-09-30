#!/usr/bin/env python3
"""Stage 9 (DeepSeek variant): the real DeepSeek-flash evaluation run.

    load corpus -> leakage preflight -> deterministic DP-22 prefilter
    -> select eligible System-1 rows -> existing model_facing_input
    -> DeepSeek adapter -> canonical results -> existing scorer/calibration/aggregation
    -> serialized evaluation artifact

This is a separate entry-point script from 09_run_evaluation.py (the Laya run), not a
generalized multi-provider runner: the two adapters have genuinely different invocation
shapes (Laya's predict_batch shares one forward pass across states; DeepSeek is an HTTP
API with only a single-item predict()), and Laya's script imports torch/laya and needs the
separate .venv, while this one needs only stdlib + a network-reachable environment.
Generalizing 09_run_evaluation.py into a parameterized multi-provider runner would be a
broader refactor than "the smallest necessary orchestration change" calls for, and that
existing, already-approved file is left untouched. Every shared pipeline module (01, 02,
04, 06, 07, 08, adapter_base) is imported and used exactly as already implemented; none
are modified. deepseek_adapter.py itself is also used completely unmodified.

Requires DEEPSEEK_API_KEY in this process's own environment (read once, at call time,
inside the injected transport function -- never printed, never written to any file).

Never writes into laya/corpus/. Writes run manifest + predictions + per-decision-type
aggregate reports under laya/results/<run_id>/.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LIB_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = LIB_DIR.parents[0] / "prompts"
RESULTS_DIR = LIB_DIR.parents[1] / "results"

sys.path.insert(0, str(LIB_DIR))
from _module_loader import load_lib_module  # noqa: E402

load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")
preflight_mod = load_lib_module("02_leakage_preflight.py", "leakage_preflight")
prefilter_mod = load_lib_module("04_deterministic_prefilter.py", "prefilter")
aggregate_mod = load_lib_module("07_aggregate_report.py", "aggregate")
serialize_mod = load_lib_module("08_serialize_result.py", "serialize")
import deepseek_adapter  # noqa: E402
from adapter_base import build_canonical_result  # noqa: E402

RESULT_SCHEMA_VERSION = "1.0"
DP22_TYPE = "agent_verification_applicable"
NON_DP22_TYPES = ["trivial_vs_staged", "documented_limitation_vs_defect", "human_acceptance_required"]
EXPECTED_CORPUS_HASH = "a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b"
EXPECTED_DP22_SYSTEM1_IDS = {"ZEUS-DP22-02", "ZEUS-DP22-03"}

DEEPSEEK_MODEL = "deepseek-flash"
DEEPSEEK_THINKING = {"type": "disabled"}
DEEPSEEK_REASONING_EFFORT = "none"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"


def _load_allowed_values(decision_type: str) -> list[str]:
    contract = json.loads((PROMPTS_DIR / f"{decision_type}.json").read_text(encoding="utf-8"))
    return contract["allowed_output_values"]


def _real_transport(request_body: dict) -> dict:
    """Reads DEEPSEEK_API_KEY at call time -- never at import time, never cached, never
    printed. Raises on any transport/HTTP failure; deepseek_adapter.DeepSeekAdapter.predict()
    is what converts that into an error PredictionEnvelope -- this function itself never
    retries and never rescues a failure."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY not present in this process's environment")
    data = json.dumps(request_body).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_ENDPOINT, data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
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

    model_identifier = deepseek_adapter.build_model_identifier(DEEPSEEK_MODEL, DEEPSEEK_THINKING, DEEPSEEK_REASONING_EFFORT)
    if model_identifier != "deepseek:deepseek-flash:thinking-disabled:effort-none":
        raise SystemExit(f"ABORT: model_identifier does not match the required literal: {model_identifier!r}")

    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise SystemExit("ABORT: DEEPSEEK_API_KEY not present in this process's environment")

    report = {
        "corpus_content_hash": corpus_hash,
        "corpus_hash_matches_expected": True,
        "decision_counts": counts,
        "model_identifier": model_identifier,
        "model_configuration": {"model": DEEPSEEK_MODEL, "thinking": DEEPSEEK_THINKING, "reasoning_effort": DEEPSEEK_REASONING_EFFORT},
        "dp22_system1_row_ids": sorted(dp22_system1_ids),
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "api_credential_present": True,
    }
    print("=== PREFLIGHT ===")
    print(json.dumps(report, indent=2))
    print()
    return report


def run() -> dict:
    pf = preflight()
    run_id = f"phase4-deepseek-flash-real-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
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

    adapter = deepseek_adapter.DeepSeekAdapter(
        transport=_real_transport, model=DEEPSEEK_MODEL,
        thinking=DEEPSEEK_THINKING, reasoning_effort=DEEPSEEK_REASONING_EFFORT,
    )

    manifest = {
        "run_id": run_id,
        "corpus_content_hash": corpus_hash,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "provider": "deepseek",
        "model": DEEPSEEK_MODEL,
        "thinking": DEEPSEEK_THINKING,
        "reasoning_effort": DEEPSEEK_REASONING_EFFORT,
        "model_identifier": model_identifier,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    all_results: list[dict] = []

    # --- DP-22: deterministic prefilter first; only system1_judgment rows go to DeepSeek ---
    dp22_rows = [r for r in rows if r.decision_type == DP22_TYPE]
    dp22_allowed = _load_allowed_values(DP22_TYPE)
    dp22_deepseek_rows = []
    for row in dp22_rows:
        prefilter_out = prefilter_mod.deterministic_prefilter(row.decision_type, load_corpus_mod.model_facing_payload(row))
        partition = row.raw.get("corpus_partition")
        if not prefilter_out["handled"] and partition == "system1_judgment":
            dp22_deepseek_rows.append(row)
        else:
            all_results.append(prefilter_mod.build_canonical_result(
                row.candidate_id, row.decision_type, run_id, corpus_hash, dp22_allowed, prefilter_out,
            ))

    if {r.candidate_id for r in dp22_deepseek_rows} != EXPECTED_DP22_SYSTEM1_IDS:
        raise SystemExit(f"ABORT: expected exactly {EXPECTED_DP22_SYSTEM1_IDS}, got {[r.candidate_id for r in dp22_deepseek_rows]}")

    def _run_deepseek_group(group_rows, decision_type):
        allowed = _load_allowed_values(decision_type)
        results = []
        for row in group_rows:
            state = load_corpus_mod.model_facing_payload(row)
            # One request per row, no retry, no rescue on failure -- deepseek_adapter's
            # own predict() already converts any transport/API/parse failure into an
            # error PredictionEnvelope rather than raising.
            envelope = adapter.predict(decision_type, state, allowed)
            results.append(build_canonical_result(row.candidate_id, decision_type, run_id, corpus_hash, envelope))
            status = "OK" if envelope.valid_prediction else f"FAIL ({envelope.error})"
            print(f"  {row.candidate_id}: {status}")
        return results

    print(f"=== DP-22 system1_judgment ({len(dp22_deepseek_rows)} rows) ===")
    all_results.extend(_run_deepseek_group(dp22_deepseek_rows, DP22_TYPE))

    for decision_type in NON_DP22_TYPES:
        group_rows = [r for r in rows if r.decision_type == decision_type]
        print(f"=== {decision_type} ({len(group_rows)} rows) ===")
        all_results.extend(_run_deepseek_group(group_rows, decision_type))

    if len(all_results) != 36:
        raise SystemExit(f"ABORT: expected 36 canonical results, produced {len(all_results)}")

    # --- serialize predictions (never into laya/corpus/) ---
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    serialize_mod.write_results_jsonl(all_results, run_dir / "predictions.jsonl")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # --- score + aggregate, per decision type (identical structure to the Laya run) ---
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
    deepseek_dp22 = [r for r in dp22_results if r["model_identifier"] == model_identifier]
    det_report = aggregate_mod.build_report(
        DP22_TYPE, deterministic_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, prefilter_mod.MODEL_IDENTIFIER,
    )
    deepseek_report = aggregate_mod.build_report(
        DP22_TYPE, deepseek_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, model_identifier,
    )
    reports[DP22_TYPE] = {
        "run_id": run_id, "corpus_content_hash": corpus_hash, "schema_version": RESULT_SCHEMA_VERSION,
        "decision_type": DP22_TYPE, "model_identifier": "mixed (see per-block model_identifier)",
        "blocks": {**det_report["blocks"], **deepseek_report["blocks"]},
    }

    (run_dir / "aggregate_report.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")

    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nWrote: {run_dir}/predictions.jsonl ({len(all_results)} rows)")
    print(f"Wrote: {run_dir}/aggregate_report.json")
    print(f"Wrote: {run_dir}/manifest.json")

    return {"run_id": run_id, "run_dir": str(run_dir), "manifest": manifest, "reports": reports, "results": all_results}


if __name__ == "__main__":
    run()
