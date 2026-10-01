#!/usr/bin/env python3
"""Deterministic validation for laya/corpus/phase-4.1-decision-corpus.jsonl.

Does not run Laya, JEV, or any model. Pure structural/data-contract checks against
the approved schema and corpus-design rules. Run: python3 laya/validate_corpus.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "harness" / "lib"))
from leakage_rules import (  # noqa: E402
    exact_copy_hits, flatten_strings, label_token_hits, paraphrase_overlap,
)

CORPUS_PATH = Path(__file__).parent / "corpus" / "phase-4.1-decision-corpus.jsonl"
SCHEMA_PATH = Path(__file__).parent / "schema" / "decision_corpus_schema.json"
EXPECTED_SCHEMA_VERSION = "1.0"

VALID_DECISION_TYPES = {
    "trivial_vs_staged", "agent_verification_applicable",
    "documented_limitation_vs_defect", "human_acceptance_required",
}
VALID_KNOWABLE_AT = {
    "before_implementation", "after_implementation", "after_verification",
    "after_human_acceptance", "not_determinable",
}
VALID_CLEAN = {"clean", "borderline", "confounded"}
VALID_INCLUSION = {"include", "include_as_borderline", "exclude"}
VALID_AMBIGUITY = {"obvious", "ambiguous", None}
VALID_PARTITION = {"deterministic_prefilter_validation", "system1_judgment", None}
VALID_POLARITY = {"positive_match", "absence_based", None}
VALID_NORMATIVE = {"required", "sufficient_without", "indeterminate", None}
VALID_EMPIRICAL = {"substantive_engagement", "bare_acknowledgment", "not_available", None}
VALID_RELATIONSHIP = {"agree", "diverge", "empirical_unavailable", None}


def load_schema_version():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh).get("schema_version")


def check_schema_version():
    actual = load_schema_version()
    if actual != EXPECTED_SCHEMA_VERSION:
        return [f"schema declares schema_version={actual!r}, expected {EXPECTED_SCHEMA_VERSION!r}"]
    return []


def load_rows(path=CORPUS_PATH):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise SystemExit(f"FAIL  line {i}: invalid JSON ({e})")
    return rows


def check_schema_fields(rows):
    required = [
        "candidate_id", "decision_type", "source_project", "source_artifact",
        "decision_time_context", "model_facing_input", "ground_truth_knowable_at",
        "clean_or_borderline", "leakage_check", "inclusion_status", "inclusion_reason",
        "eligible_for_binary_scoring", "ground_truth_evidence",
    ]
    errors = []
    for r in rows:
        missing = [f for f in required if f not in r]
        if missing:
            errors.append(f"{r.get('candidate_id', '?')}: missing fields {missing}")
        if r.get("decision_type") not in VALID_DECISION_TYPES:
            errors.append(f"{r.get('candidate_id')}: invalid decision_type {r.get('decision_type')!r}")
        if r.get("ground_truth_knowable_at") not in VALID_KNOWABLE_AT:
            errors.append(f"{r.get('candidate_id')}: invalid ground_truth_knowable_at")
        if r.get("clean_or_borderline") not in VALID_CLEAN:
            errors.append(f"{r.get('candidate_id')}: invalid clean_or_borderline")
        if r.get("inclusion_status") not in VALID_INCLUSION:
            errors.append(f"{r.get('candidate_id')}: invalid inclusion_status")
        if r.get("ambiguity_tier") not in VALID_AMBIGUITY:
            errors.append(f"{r.get('candidate_id')}: invalid ambiguity_tier")
        if r.get("corpus_partition") not in VALID_PARTITION:
            errors.append(f"{r.get('candidate_id')}: invalid corpus_partition")
        if r.get("evidence_polarity") not in VALID_POLARITY:
            errors.append(f"{r.get('candidate_id')}: invalid evidence_polarity")
        if r.get("normative_label") not in VALID_NORMATIVE:
            errors.append(f"{r.get('candidate_id')}: invalid normative_label")
        if r.get("empirical_label") not in VALID_EMPIRICAL:
            errors.append(f"{r.get('candidate_id')}: invalid empirical_label")
        if r.get("normative_empirical_relationship") not in VALID_RELATIONSHIP:
            errors.append(f"{r.get('candidate_id')}: invalid normative_empirical_relationship")
        if r.get("clean_or_borderline") == "confounded" and not r.get("confound_reason"):
            errors.append(f"{r.get('candidate_id')}: confounded row missing confound_reason")
        ge = r.get("ground_truth_evidence")
        if not isinstance(ge, dict) or not all(k in ge for k in ("quote", "citation", "verification_method")):
            errors.append(f"{r.get('candidate_id')}: ground_truth_evidence missing required subfields")
    return errors


def check_model_input_derivable(rows):
    """Every fact in model_facing_input must be traceable to decision_time_context.
    Deterministic proxy: every string appearing in model_facing_input must appear
    verbatim somewhere inside decision_time_context (substring match)."""
    errors = []
    for r in rows:
        ctx_strings = list(flatten_strings(r.get("decision_time_context")))
        ctx_blob = "\n".join(ctx_strings)
        for s in flatten_strings(r.get("model_facing_input")):
            if s not in ctx_blob:
                errors.append(f"{r['candidate_id']}: model_facing_input string not found in decision_time_context: {s[:80]!r}")
    return errors


def check_leakage_excluded(rows):
    """Exact-copy leakage (hard fail): ground_truth_evidence.quote, empirical_basis, and
    normative_basis must never appear verbatim inside model_facing_input. Also hard-fails
    if a label enum value itself (e.g. "sufficient_without", "deliberate") appears literally
    in model_facing_input -- these tokens are distinctive enough that literal presence is
    unambiguous leakage, not ordinary word overlap."""
    errors = []
    for r in rows:
        mfi_blob = "\n".join(flatten_strings(r.get("model_facing_input")))
        ge = r.get("ground_truth_evidence") or {}
        leak_fields = {"ground_truth_evidence.quote": ge.get("quote", "")}
        if r.get("empirical_basis"):
            leak_fields["empirical_basis"] = r["empirical_basis"]
        if r.get("normative_basis"):
            leak_fields["normative_basis"] = r["normative_basis"]
        for field_name in exact_copy_hits(mfi_blob, leak_fields):
            errors.append(f"{r['candidate_id']}: exact copy of {field_name} found inside model_facing_input")
        # documented_limitation_vs_defect is exempt: its model_facing_input legitimately
        # includes the quoted decision-document excerpt as intentional input (the whole task
        # is "does this quoted text cover the behavior"), so that excerpt may naturally use a
        # word like "deliberate" in its own prose without that being answer injection -- the
        # word is the source document's, not ours.
        own_labels = {
            str(r.get("ground_truth_label") or "").replace("_", " ").lower(),
            str(r.get("normative_label") or "").replace("_", " ").lower(),
            str(r.get("empirical_label") or "").replace("_", " ").lower(),
        }
        exempt = r["decision_type"] == "documented_limitation_vs_defect"
        for tok in label_token_hits(mfi_blob, own_labels, exempt=exempt):
            errors.append(f"{r['candidate_id']}: model_facing_input literally contains its own label token {tok!r}")
        if not r.get("leakage_check", {}).get("passed"):
            errors.append(f"{r['candidate_id']}: leakage_check.passed is not true")
    return errors


def check_answer_adjacent_paraphrase(rows):
    """HEURISTIC ONLY -- not a proof of leakage or its absence. Flags rows where
    model_facing_input shares a high fraction of significant (non-stopword, len>3) words
    with normative_basis / ground_truth_evidence.quote / empirical_basis, which can indicate
    a reworded paraphrase of the answer rather than neutral decision-time context.

    Known limitations, stated rather than hidden: this cannot detect a paraphrase that shares
    no vocabulary with the source field (e.g. a fully reworded restatement using different
    words for the same idea), and it can false-positive when a field and the input legitimately
    share ordinary domain vocabulary (e.g. both mention "the feature" or "the repository").
    Results are reported as WARNINGS for human review, never as a validation failure, because
    a deterministic word-overlap ratio cannot reliably establish semantic equivalence either way.
    """
    warnings = []
    for r in rows:
        mfi_blob = " ".join(flatten_strings(r.get("model_facing_input")))
        sources = {
            "normative_basis": r.get("normative_basis"),
            "ground_truth_evidence.quote": (r.get("ground_truth_evidence") or {}).get("quote"),
            "empirical_basis": r.get("empirical_basis"),
        }
        for field_name, text in sources.items():
            if not text:
                continue
            overlap = paraphrase_overlap(mfi_blob, text)
            if overlap is not None and overlap >= 0.5:
                warnings.append(
                    f"{r['candidate_id']}: {overlap:.0%} of {field_name}'s significant words "
                    f"also appear in model_facing_input -- possible paraphrase leakage, "
                    f"needs human review (heuristic signal only, not proof)"
                )
    return warnings


def check_unique_ids(rows):
    seen = {}
    errors = []
    for r in rows:
        cid = r.get("candidate_id")
        if cid in seen:
            errors.append(f"duplicate candidate_id: {cid}")
        seen[cid] = True
    return errors


def check_inclusion_status_consistency(rows):
    """Schema contract (ADR-008): eligible_for_binary_scoring may be true only for a row that
    is both clean_or_borderline == "clean" and inclusion_status == "include"."""
    errors = []
    for r in rows:
        if not r.get("eligible_for_binary_scoring"):
            continue
        if r["inclusion_status"] != "include":
            errors.append(f"{r['candidate_id']}: inclusion_status={r['inclusion_status']!r} row must not be "
                          f"eligible_for_binary_scoring (only clean, include rows may be eligible)")
        if r["clean_or_borderline"] != "clean":
            errors.append(f"{r['candidate_id']}: clean_or_borderline={r['clean_or_borderline']!r} row must not be "
                          f"eligible_for_binary_scoring (only clean, include rows may be eligible)")
    return errors


def check_dp23_fields(rows):
    errors = []
    for r in rows:
        if r["decision_type"] == "human_acceptance_required":
            if r.get("ground_truth_label") is not None:
                errors.append(f"{r['candidate_id']}: human_acceptance_required must not set ground_truth_label (use normative_label/empirical_label)")
            if r.get("normative_label") is None or r.get("empirical_label") is None:
                errors.append(f"{r['candidate_id']}: missing normative_label or empirical_label")
            if r.get("empirical_label") == "not_available" and r.get("normative_empirical_relationship") != "empirical_unavailable":
                errors.append(f"{r['candidate_id']}: empirical_label=not_available must set relationship=empirical_unavailable")
        else:
            if r.get("normative_label") is not None or r.get("empirical_label") is not None:
                errors.append(f"{r['candidate_id']}: non-DP23 row must not set normative_label/empirical_label")
    return errors


def check_dp11_no_clean_trivial(rows):
    """Adjustment 1: DP-11 must have no clean 'trivial' example, and no DP-11 row may
    be eligible for binary scoring."""
    errors = []
    for r in rows:
        if r["decision_type"] != "trivial_vs_staged":
            continue
        if r.get("eligible_for_binary_scoring"):
            errors.append(f"{r['candidate_id']}: trivial_vs_staged row must never be eligible_for_binary_scoring")
        if r.get("ground_truth_label") == "trivial" and r["clean_or_borderline"] == "clean":
            errors.append(f"{r['candidate_id']}: found a CLEAN trivial-class example -- this contradicts the established evidence gap and must be re-checked, not silently accepted")
    return errors


def check_dp16_polarity(rows):
    errors = []
    for r in rows:
        if r["decision_type"] == "documented_limitation_vs_defect":
            if r.get("evidence_polarity") is None and r["inclusion_status"] != "exclude":
                errors.append(f"{r['candidate_id']}: documented_limitation_vs_defect row missing evidence_polarity")
    return errors


def check_dp22_partitions(rows):
    errors = []
    for r in rows:
        if r["decision_type"] != "agent_verification_applicable":
            continue
        if r["inclusion_status"] == "exclude":
            continue
        if r.get("ambiguity_tier") == "obvious" and r.get("corpus_partition") == "system1_judgment":
            errors.append(f"{r['candidate_id']}: an OBVIOUS case must not be placed in the system1_judgment partition")
        if r.get("ambiguity_tier") == "ambiguous" and r.get("corpus_partition") == "deterministic_prefilter_validation":
            errors.append(f"{r['candidate_id']}: an AMBIGUOUS case must not be placed in the deterministic_prefilter_validation partition")
    return errors


def main():
    rows = load_rows()
    checks = [
        ("schema_version matches expected", check_schema_version()),
        ("schema fields valid", check_schema_fields(rows)),
        ("model_facing_input derivable from decision_time_context", check_model_input_derivable(rows)),
        ("post-decision evidence excluded from model_facing_input", check_leakage_excluded(rows)),
        ("candidate_id uniqueness", check_unique_ids(rows)),
        ("inclusion_status / scoring-eligibility consistency", check_inclusion_status_consistency(rows)),
        ("DP-23 normative/empirical field structure", check_dp23_fields(rows)),
        ("DP-11 has no clean trivial example, never scoring-eligible", check_dp11_no_clean_trivial(rows)),
        ("DP-16 evidence_polarity present", check_dp16_polarity(rows)),
        ("DP-22 pre-filter vs ambiguous partition separation", check_dp22_partitions(rows)),
    ]

    fail = 0
    for name, errors in checks:
        if errors:
            fail = 1
            print(f"FAIL  {name} ({len(errors)} issue(s))")
            for e in errors:
                print(f"      - {e}")
        else:
            print(f"PASS  {name}")

    warnings = check_answer_adjacent_paraphrase(rows)
    print()
    if warnings:
        print(f"WARN  answer-adjacent paraphrase heuristic ({len(warnings)} flagged for human review; "
              f"this is a non-exhaustive heuristic, not a pass/fail check -- see docstring)")
        for w in warnings:
            print(f"      - {w}")
    else:
        print("INFO  answer-adjacent paraphrase heuristic: nothing flagged (heuristic only -- "
              "absence of a flag is not proof of no leakage)")

    print()
    print(f"Total rows: {len(rows)}")
    from collections import Counter
    print("By decision_type:", dict(Counter(r["decision_type"] for r in rows)))
    print("By inclusion_status:", dict(Counter(r["inclusion_status"] for r in rows)))
    print("By clean_or_borderline:", dict(Counter(r["clean_or_borderline"] for r in rows)))

    if fail:
        print("\nSome validation checks FAILED.")
    else:
        print("\nAll validation checks passed.")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
