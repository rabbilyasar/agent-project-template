#!/usr/bin/env python3
"""Stage 9: the real Laya evaluation run.

    load corpus -> leakage preflight -> deterministic DP-22 prefilter
    -> select eligible System-1 rows -> existing model_facing_input
    -> Laya adapter -> canonical results -> existing scorer/calibration/aggregation
    -> serialized evaluation artifact

Single, hardcoded, procedural script for this one run -- no plugin registry, no
multi-adapter routing, no config system, no caching. Every Slice 1/2 module (01, 02, 04,
05, 06, 07, 08) is imported and used exactly as already implemented; none are modified.

Must be run with an interpreter that has `torch`/`laya` installed, e.g.:
    /home/rabbil/experiments/laya-smoke/.venv/bin/python laya/harness/lib/09_run_evaluation.py

Never writes into laya/corpus/. Writes run manifest + predictions + per-decision-type
aggregate reports under laya/results/<run_id>/.
"""
from __future__ import annotations

import json
import sys
import warnings
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
score_mod = load_lib_module("06_score.py", "score")
aggregate_mod = load_lib_module("07_aggregate_report.py", "aggregate")
serialize_mod = load_lib_module("08_serialize_result.py", "serialize")
laya_adapter = load_lib_module("laya_adapter.py", "laya_adapter")
from adapter_base import build_canonical_result  # noqa: E402

RESULT_SCHEMA_VERSION = "1.0"
DP22_TYPE = "agent_verification_applicable"
NON_DP22_TYPES = ["trivial_vs_staged", "documented_limitation_vs_defect", "human_acceptance_required"]


def _load_allowed_values(decision_type: str) -> list[str]:
    contract = json.loads((PROMPTS_DIR / f"{decision_type}.json").read_text(encoding="utf-8"))
    return contract["allowed_output_values"]


def run() -> dict:
    run_id = f"phase4.5-laya-real-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    # --- load corpus ---
    rows, corpus_hash = load_corpus_mod.load_corpus()
    if len(rows) != 36:
        raise SystemExit(f"ABORT: expected 36 corpus rows, loaded {len(rows)}")
    corpus_rows_by_id = {r.candidate_id: r.raw for r in rows}

    # --- leakage preflight, every row, before any model call ---
    for row in rows:
        rendered = str(load_corpus_mod.model_facing_payload(row))
        result = preflight_mod.check_leakage(rendered, row.raw)
        if not result.passed:
            raise SystemExit(f"ABORT: leakage preflight failed for {row.candidate_id}: {result.hard_failures}")

    # --- load the real Laya agent (fails clearly, never falls back to CPU) ---
    captured_warnings: list[str] = []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import laya as laya_pkg

        agent = laya_adapter.load_laya_agent("convaiinnovations/laya-typed-decisions", device="cuda")
        captured_warnings = [str(w.message) for w in caught]

    model_identifier = laya_adapter.build_model_identifier(laya_pkg.__version__, "convaiinnovations/laya-typed-decisions")
    adapter = laya_adapter.LayaAdapter(agent, model_identifier)

    manifest = {
        "run_id": run_id,
        "corpus_content_hash": corpus_hash,
        "result_schema_version": RESULT_SCHEMA_VERSION,
        "deterministic_prefilter_rule_version": prefilter_mod.RULE_VERSION,
        "laya_version": laya_pkg.__version__,
        "checkpoint": "convaiinnovations/laya-typed-decisions",
        "model_identifier": model_identifier,
        "device": "cuda",
        "fast": False,
        "accelerate_used": False,
        "batch_size": None,
        "sort_by_length": False,
        "pytorch_version": None,
        "hip_version": None,
        "gpu_name": None,
        "load_time_warnings": captured_warnings,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        import torch

        manifest["pytorch_version"] = torch.__version__
        manifest["hip_version"] = torch.version.hip
        manifest["gpu_name"] = torch.cuda.get_device_name(0)
    except Exception:
        pass

    print("=== run manifest (before evaluation) ===")
    print(json.dumps(manifest, indent=2))

    all_results: list[dict] = []

    # --- DP-22: deterministic prefilter first; only system1_judgment rows go to Laya ---
    dp22_rows = [r for r in rows if r.decision_type == DP22_TYPE]
    dp22_allowed = _load_allowed_values(DP22_TYPE)
    dp22_laya_rows = []
    for row in dp22_rows:
        prefilter_out = prefilter_mod.deterministic_prefilter(row.decision_type, load_corpus_mod.model_facing_payload(row))
        partition = row.raw.get("corpus_partition")
        eligible = laya_adapter.is_eligible_for_laya(row.decision_type, partition)
        if not prefilter_out["handled"] and eligible:
            dp22_laya_rows.append(row)
        else:
            # Handled by the deterministic rule, OR deferred but not escalated to Laya
            # (deterministic_prefilter_validation rows the rule failed to classify, and
            # the excluded RP-DP22-01) -- both recorded via the existing, unmodified
            # 04_deterministic_prefilter.build_canonical_result, never sent to Laya.
            all_results.append(prefilter_mod.build_canonical_result(
                row.candidate_id, row.decision_type, run_id, corpus_hash, dp22_allowed, prefilter_out,
            ))

    if len(dp22_laya_rows) != 2 or {r.candidate_id for r in dp22_laya_rows} != {"ZEUS-DP22-02", "ZEUS-DP22-03"}:
        raise SystemExit(f"ABORT: expected exactly ZEUS-DP22-02/03 eligible for Laya, got {[r.candidate_id for r in dp22_laya_rows]}")

    def _run_laya_group(group_rows, decision_type):
        states = [load_corpus_mod.model_facing_payload(r) for r in group_rows]
        allowed = _load_allowed_values(decision_type)
        envelopes = adapter.predict_batch(decision_type, states, allowed)
        return [
            build_canonical_result(row.candidate_id, decision_type, run_id, corpus_hash, envelope)
            for row, envelope in zip(group_rows, envelopes)
        ]

    all_results.extend(_run_laya_group(dp22_laya_rows, DP22_TYPE))

    # --- DP-11, DP-16, DP-23: no deterministic rule, all rows go to Laya, grouped by type ---
    for decision_type in NON_DP22_TYPES:
        group_rows = [r for r in rows if r.decision_type == decision_type]
        all_results.extend(_run_laya_group(group_rows, decision_type))

    if len(all_results) != 36:
        raise SystemExit(f"ABORT: expected 36 canonical results, produced {len(all_results)}")

    # --- serialize predictions (never into laya/corpus/) ---
    run_dir = RESULTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    serialize_mod.write_results_jsonl(all_results, run_dir / "predictions.jsonl")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # --- score + aggregate, per decision type ---
    results_by_type: dict[str, list[dict]] = {}
    for r in all_results:
        results_by_type.setdefault(r["decision_type"], []).append(r)

    reports: dict[str, dict] = {}

    # DP-11: not_scored regardless; feed every attempted row (qualitative review only).
    reports["trivial_vs_staged"] = aggregate_mod.build_report(
        "trivial_vs_staged", results_by_type.get("trivial_vs_staged", []), corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    # DP-16: exclude inclusion_status="exclude" rows from the scored aggregate (a corpus-
    # authoring-time fact, decided before any Laya prediction existed) -- still recorded
    # in predictions.jsonl above.
    dp16_scoring_eligible = [
        r for r in results_by_type.get("documented_limitation_vs_defect", [])
        if corpus_rows_by_id[r["candidate_id"]]["inclusion_status"] != "exclude"
    ]
    reports["documented_limitation_vs_defect"] = aggregate_mod.build_report(
        "documented_limitation_vs_defect", dp16_scoring_eligible, corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    # DP-23: same exclude-filter (currently a no-op, 0 excluded DP-23 rows, applied for
    # consistency/robustness).
    dp23_scoring_eligible = [
        r for r in results_by_type.get("human_acceptance_required", [])
        if corpus_rows_by_id[r["candidate_id"]]["inclusion_status"] != "exclude"
    ]
    reports["human_acceptance_required"] = aggregate_mod.build_report(
        "human_acceptance_required", dp23_scoring_eligible, corpus_rows_by_id,
        run_id, corpus_hash, RESULT_SCHEMA_VERSION, model_identifier,
    )

    # DP-22: two systems contributed -- build each partition's block with its OWN
    # model_identifier via two separate calls (existing by_partition bucketing already
    # discards whichever partition isn't present in a given results subset, so no new
    # filtering code is needed), then merge the two blocks dicts. No code change to
    # 07_aggregate_report.py.
    dp22_results = results_by_type.get(DP22_TYPE, [])
    deterministic_dp22 = [r for r in dp22_results if r["model_identifier"] == prefilter_mod.MODEL_IDENTIFIER]
    laya_dp22 = [r for r in dp22_results if r["model_identifier"] == model_identifier]
    det_report = aggregate_mod.build_report(
        DP22_TYPE, deterministic_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, prefilter_mod.MODEL_IDENTIFIER,
    )
    laya_report = aggregate_mod.build_report(
        DP22_TYPE, laya_dp22, corpus_rows_by_id, run_id, corpus_hash,
        RESULT_SCHEMA_VERSION, model_identifier,
    )
    reports[DP22_TYPE] = {
        "run_id": run_id, "corpus_content_hash": corpus_hash, "schema_version": RESULT_SCHEMA_VERSION,
        "decision_type": DP22_TYPE, "model_identifier": "mixed (see per-block model_identifier)",
        "blocks": {**det_report["blocks"], **laya_report["blocks"]},
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
