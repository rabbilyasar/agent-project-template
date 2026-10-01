#!/usr/bin/env python3
"""Self-tests for lib/10_rescore_offline.py: the ADR-008 eligibility-only corpus-correction
check, prediction coverage, and DP-23 class-coverage behaviour against the real corrected
corpus. Synthetic corpora and predictions only; no model, network, or credential access."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _fixtures import canonical_result
from _load_lib import load_lib_module

rescore = load_lib_module("10_rescore_offline.py", "rescore_offline")
load_corpus = load_lib_module("01_load_corpus.py", "load_corpus")

FORBIDDEN_MODULES = ("torch", "laya", "anthropic", "openai", "requests", "httpx", "urllib.request",
                     "http.client", "claude_adapter", "deepseek_adapter", "laya_adapter")


def _jsonl(rows: list[dict]) -> bytes:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8")


def _correction(original: bytes, corrected: bytes) -> dict:
    return {
        "original_corpus_sha256": hashlib.sha256(original).hexdigest(),
        "corrected_corpus_sha256": hashlib.sha256(corrected).hexdigest(),
        "candidate_id": "B", "field": "eligible_for_binary_scoring", "from": True, "to": False,
    }


def _rejects(original_rows: list[dict], corrected_rows: list[dict], correction: dict | None = None) -> bool:
    original, corrected = _jsonl(original_rows), _jsonl(corrected_rows)
    try:
        rescore.verify_eligibility_only_correction(original, corrected, correction or _correction(original, corrected))
    except rescore.CorpusDiffError:
        return True
    return False


def _aborts(fn, *args) -> bool:
    try:
        fn(*args)
    except SystemExit:
        return True
    return False


def main() -> int:
    checks = []

    base = [
        {"candidate_id": "A", "normative_label": "required", "eligible_for_binary_scoring": True, "model_facing_input": {"x": 1}},
        {"candidate_id": "B", "normative_label": "sufficient_without", "eligible_for_binary_scoring": True, "model_facing_input": {"x": 2}},
        {"candidate_id": "C", "normative_label": "required", "eligible_for_binary_scoring": True, "model_facing_input": {"x": 3}},
    ]

    def edit(**changes_by_id) -> list[dict]:
        return [{**r, **changes_by_id.get(r["candidate_id"], {})} for r in base]

    approved = edit(B={"eligible_for_binary_scoring": False})
    checks.append(("approved eligibility-only correction is accepted", not _rejects(base, approved)))
    checks.append(("an unrelated field change on the corrected row is rejected",
                   _rejects(base, edit(B={"eligible_for_binary_scoring": False, "normative_label": "required"}))))
    checks.append(("an additional change on another row is rejected",
                   _rejects(base, edit(B={"eligible_for_binary_scoring": False}, C={"model_facing_input": {"x": 4}}))))
    checks.append(("a different row's eligibility change is rejected",
                   _rejects(base, edit(C={"eligible_for_binary_scoring": False}))))
    checks.append(("an unchanged corpus (correction missing) is rejected", _rejects(base, base)))
    wrong_hash = {**_correction(_jsonl(base), _jsonl(approved)), "original_corpus_sha256": "0" * 64}
    checks.append(("a corpus hash mismatch is rejected", _rejects(base, approved, wrong_hash)))
    checks.append(("row reordering is rejected", _rejects(base, [approved[1], approved[0], approved[2]])))
    checks.append(("an added row is rejected", _rejects(base, approved + [{**base[0], "candidate_id": "D"}])))
    checks.append(("true -> 1 is not treated as an unchanged value",
                   _rejects(base, edit(A={"eligible_for_binary_scoring": 1}, B={"eligible_for_binary_scoring": False}))))

    # The pinned ADR-008 correction matches the real git original and the working corpus.
    pinned = rescore.ADR008_CORRECTION
    original = subprocess.run(
        ["git", "-C", str(rescore.REPO_DIR), "show", f"{pinned['original_corpus_git_rev']}:{rescore.CORPUS_REL_PATH}"],
        capture_output=True, check=True,
    ).stdout
    try:
        rescore.verify_eligibility_only_correction(original, load_corpus.CORPUS_PATH.read_bytes(), pinned)
        checks.append(("real original -> corrected corpus is exactly the ADR-008 correction", True))
    except rescore.CorpusDiffError as exc:
        print(f"      real-corpus diff: {exc}")
        checks.append(("real original -> corrected corpus is exactly the ADR-008 correction", False))

    # Prediction coverage: only manifest-listed, inclusion_status=exclude rows may be absent.
    rows = {"A": {"inclusion_status": "include"}, "X": {"inclusion_status": "exclude"}}
    preds = [{"candidate_id": "A"}]
    checks.append(("listed excluded skip is allowed", not _aborts(rescore.check_prediction_coverage, preds, rows, ["X"])))
    checks.append(("unlisted missing row aborts", _aborts(rescore.check_prediction_coverage, preds, rows, [])))
    checks.append(("missing non-exclude row aborts even if listed",
                   _aborts(rescore.check_prediction_coverage, [{"candidate_id": "X"}], rows, ["A"])))
    checks.append(("duplicate prediction aborts", _aborts(rescore.check_prediction_coverage, preds * 2 + [{"candidate_id": "X"}], rows, [])))

    # Integration: real corrected corpus, synthetic all-"correct" predictions.
    corpus_rows, corpus_hash = load_corpus.load_corpus()
    by_id = {r.candidate_id: r.raw for r in corpus_rows}
    target = {"human_acceptance_required": "normative_label"}
    predictions = [
        canonical_result(r.candidate_id, r.decision_type, r.raw.get(target.get(r.decision_type, "ground_truth_label")) or "staged",
                         run_id="itest", corpus_hash=corpus_hash)
        for r in corpus_rows
    ]
    reports = rescore.build_reports(predictions, by_id, corpus_hash, "1.0")
    dp23 = reports["human_acceptance_required"]
    checks.append(("corrected corpus: AGENT-DP23-01 is ineligible", by_id["AGENT-DP23-01"]["eligible_for_binary_scoring"] is False))
    checks.append(("corrected corpus: DP-23 is single-class and not_scored, even with every prediction right",
                   dp23["not_scored"] is True and dp23["accuracy"] is None and dp23["n"] == 9
                   and dp23["eligible_ground_truth_classes"] == ["required"]
                   and "AGENT-DP23-01" in dp23["binary_scoring_ineligible_ids"]))
    checks.append(("corrected corpus: DP-11 stays not_scored", reports["trivial_vs_staged"]["not_scored"] is True))
    checks.append(("corrected corpus: DP-16 and DP-22 System-1 are still scored",
                   reports["documented_limitation_vs_defect"]["blocks"]["overall"]["accuracy"] == 1.0
                   and reports["agent_verification_applicable"]["blocks"]["system1_judgment"]["accuracy"] == 1.0))

    checks.append(("rescore path imports no model runtime, adapter, or HTTP client",
                   not [m for m in FORBIDDEN_MODULES if m in sys.modules]))
    source = Path(rescore.__file__).read_text(encoding="utf-8")
    checks.append(("rescore module reads no environment variables or API keys",
                   "environ" not in source and "getenv" not in source and "API_KEY" not in source))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  rescore offline checks failed: {failed}")
        return 1
    print(f"PASS  rescore offline: {len(checks)} checks, zero model/API calls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
