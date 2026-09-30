#!/usr/bin/env python3
"""Stage 4: deterministic prefilter baseline.

A minimal, frozen, path-pattern rule for agent_verification_applicable (DP-22) only.
Every other decision_type defers to system-1 unconditionally -- this slice does not invent
deterministic rules beyond the one already approved.

The rule was designed from generic, ecosystem-wide file-extension and directory-keyword
conventions (frontend component/asset extensions and directory names vs. backend-only
data-access/persistence markers), not fit to this corpus's ground truth: it takes only
files_touched as input and never receives a ground_truth/normative/empirical field. Some
real corpus rows in the deterministic_prefilter_validation partition (an empty files_touched
list, or an inherently dual-purpose directory name like "views/") legitimately defer under
this rule rather than being forced to an answer -- that is an honest limitation of a
minimal v1.0 baseline, not a bug, and this slice does not expand the rule to close that gap
(see AGENTS.md -- do not tune rules based on model behavior).

Rule version is frozen at "1.0" for the first evaluation. Any future change to the pattern
lists is a new rule_version, not a silent edit of this one.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

RULE_VERSION = "1.0"
MODEL_IDENTIFIER = f"deterministic_prefilter_v{RULE_VERSION}"

FRONTEND_EXTENSIONS = (
    ".tsx", ".jsx", ".vue", ".svelte", ".html", ".htm", ".css", ".scss", ".less",
)
FRONTEND_KEYWORDS = (
    "frontend", "component", "/ui/", "client/", "/pages/", "/public/", "/static/",
)
BACKEND_ONLY_KEYWORDS = (
    "repository", "/models/", "models.py", "migration", "/db/", "database", ".sql",
)


def classify_dp22(files_touched: list[str] | None) -> dict:
    """Ground truth is never passed in or consulted here -- this function's only input is
    the list of touched file paths from model_facing_input."""
    blob = " ".join(files_touched or []).lower()
    if not blob.strip():
        return {
            "handled": False, "predicted_value": None,
            "reason": "no files_touched signal to classify", "rule_version": RULE_VERSION,
        }
    if any(ext in blob for ext in FRONTEND_EXTENSIONS) or any(kw in blob for kw in FRONTEND_KEYWORDS):
        return {
            "handled": True, "predicted_value": "applicable",
            "reason": "path matches a known frontend file extension or directory keyword",
            "rule_version": RULE_VERSION,
        }
    if any(kw in blob for kw in BACKEND_ONLY_KEYWORDS):
        return {
            "handled": True, "predicted_value": "not_applicable",
            "reason": "path matches a known backend-only keyword with no frontend marker present",
            "rule_version": RULE_VERSION,
        }
    return {
        "handled": False, "predicted_value": None,
        "reason": "path does not match a known frontend or backend-only pattern",
        "rule_version": RULE_VERSION,
    }


def deterministic_prefilter(decision_type: str, model_facing_input: dict) -> dict:
    """Entry point for any decision_type. Only agent_verification_applicable has an
    approved deterministic rule; everything else defers to system-1 unconditionally."""
    if decision_type != "agent_verification_applicable":
        return {
            "handled": False, "predicted_value": None,
            "reason": f"no deterministic rule is defined for decision_type={decision_type!r}",
            "rule_version": RULE_VERSION,
        }
    files_touched = (model_facing_input or {}).get("files_touched")
    return classify_dp22(files_touched)


def build_canonical_result(
    candidate_id: str, decision_type: str, run_id: str, corpus_content_hash: str,
    allowed_output_values: list[str], prefilter_output: dict, latency_ms: float | None = None,
    timestamp: str | None = None,
) -> dict:
    """Converts a deterministic prefilter decision into the canonical result format
    (laya/schema/result_schema.json). Deferred cases (handled=False) still produce a
    canonical result with predicted_value=None and valid_prediction=False -- there is no
    system-1 to hand off to in this model-free slice, so a deferral is simply an unattempted
    prediction, not an error (nothing malfunctioned)."""
    predicted_value = prefilter_output["predicted_value"]
    valid = predicted_value is not None and predicted_value in allowed_output_values
    if predicted_value is not None and not valid:
        raise ValueError(
            f"{candidate_id}: deterministic prefilter produced {predicted_value!r}, "
            f"which is not one of the allowed_output_values {allowed_output_values} -- "
            f"refusing to coerce it into a valid prediction"
        )
    return {
        "candidate_id": candidate_id,
        "decision_type": decision_type,
        "run_id": run_id,
        "model_identifier": MODEL_IDENTIFIER,
        "predicted_value": predicted_value,
        "valid_prediction": valid,
        "confidence": None,
        "probability_distribution": None,
        "latency_ms": latency_ms,
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
        "error": None,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "corpus_content_hash": corpus_content_hash,
        "raw_response": prefilter_output,
    }


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _module_loader import load_lib_module
    load_corpus = load_lib_module("01_load_corpus.py", "load_corpus")

    rows, corpus_hash = load_corpus.load_corpus()
    dp22_rows = [r for r in rows if r.decision_type == "agent_verification_applicable"]
    handled = 0
    for row in dp22_rows:
        out = deterministic_prefilter(row.decision_type, load_corpus.model_facing_payload(row))
        status = "HANDLED" if out["handled"] else "DEFER  "
        print(f"{status} {row.candidate_id}: predicted={out['predicted_value']!r} ({out['reason']})")
        if out["handled"]:
            handled += 1
    print(f"\n{handled}/{len(dp22_rows)} agent_verification_applicable rows handled by the deterministic rule; rest defer to system-1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
