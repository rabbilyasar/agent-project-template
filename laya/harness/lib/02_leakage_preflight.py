#!/usr/bin/env python3
"""Stage 2: evaluation-time leakage preflight.

Given a rendered prompt string (whatever text is about to be sent to a deterministic
rule, Claude, Laya, or JEV) and the corpus row it was built from, hard-fails if any
prohibited field's value is found verbatim in the rendered text, or if a literal label
token matching this row's own answer is present. Paraphrase is a WARN-only signal via
the same heuristic laya/validate_corpus.py already uses -- never a hard failure.

Independent of any adapter: this module knows nothing about Claude, Laya, or JEV. It is
called on the exact string that would be sent, right before sending it, by whichever
adapter renders that string -- adapters are not implemented in this slice.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leakage_rules import exact_copy_hits, label_token_hits, paraphrase_overlap  # noqa: E402

# Every field whose value must never appear verbatim in a rendered prompt, beyond the
# corpus-authoring-time set validate_corpus.py already checks (ground_truth_evidence.quote,
# normative_basis, empirical_basis). candidate_id is evaluation-time-specific: it is legitimate
# corpus/result bookkeeping but must never leak into the text actually sent to a model.
EXACT_MATCH_FIELDS = (
    "ground_truth_label", "normative_label", "empirical_label",
    "ground_truth_evidence.quote", "ground_truth_evidence.citation",
    "normative_basis", "empirical_basis",
    "inclusion_status", "inclusion_reason", "clean_or_borderline",
    "corpus_partition", "ambiguity_tier", "evidence_polarity", "reused_evidence_of",
    "candidate_id",
)


class LeakagePreflightFailure(Exception):
    """Raised by check_leakage()'s caller-facing helper when a hard failure is found.
    Machine-readable: str(exception) is the same text as result.hard_failures, joined."""


@dataclass
class PreflightResult:
    passed: bool
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _get(row_raw: dict, dotted_field: str):
    if "." in dotted_field:
        top, sub = dotted_field.split(".", 1)
        return (row_raw.get(top) or {}).get(sub)
    return row_raw.get(dotted_field)


def check_leakage(rendered_prompt: str, row_raw: dict) -> PreflightResult:
    """row_raw is a corpus row's full dict (CorpusRow.raw from the loader) -- this
    function is deliberately given the whole row, not just the forbidden fields, so it
    can decide per-decision-type exemptions the same way validate_corpus.py does."""
    hard_failures: list[str] = []

    # candidate_id is checked unconditionally, bypassing the length gate the generic
    # exact_copy_hits check applies: it is a precise, unambiguous identifier (e.g.
    # "ZEUS-DP22-03"), not a coincidental short word, and must never appear in a
    # rendered prompt regardless of length.
    candidate_id = row_raw.get("candidate_id")
    if candidate_id and candidate_id.lower() in rendered_prompt.lower():
        hard_failures.append("candidate_id found in rendered prompt")

    exact_fields = {name: _get(row_raw, name) for name in EXACT_MATCH_FIELDS if name != "candidate_id"}
    for name in exact_copy_hits(rendered_prompt, exact_fields):
        hard_failures.append(f"exact copy of {name} found in rendered prompt")

    # leakage_check is itself an object ({"passed": bool, "note": str}); its note is
    # free text authored about the row, not something a model should ever see either.
    lc_note = (row_raw.get("leakage_check") or {}).get("note")
    if lc_note and len(lc_note) > 20 and lc_note.lower() in rendered_prompt.lower():
        hard_failures.append("exact copy of leakage_check.note found in rendered prompt")

    own_labels = {
        str(row_raw.get("ground_truth_label") or "").replace("_", " ").lower(),
        str(row_raw.get("normative_label") or "").replace("_", " ").lower(),
        str(row_raw.get("empirical_label") or "").replace("_", " ").lower(),
    }
    exempt = row_raw.get("decision_type") == "documented_limitation_vs_defect"
    for tok in label_token_hits(rendered_prompt, own_labels, exempt=exempt):
        hard_failures.append(f"rendered prompt literally contains its own label token {tok!r}")

    warnings: list[str] = []
    for name in ("normative_basis", "empirical_basis"):
        text = row_raw.get(name)
        if not text:
            continue
        overlap = paraphrase_overlap(rendered_prompt, text)
        if overlap is not None and overlap >= 0.5:
            warnings.append(f"{overlap:.0%} of {name}'s significant words also appear in the rendered prompt")
    ge_quote = (row_raw.get("ground_truth_evidence") or {}).get("quote")
    if ge_quote:
        overlap = paraphrase_overlap(rendered_prompt, ge_quote)
        if overlap is not None and overlap >= 0.5:
            warnings.append(f"{overlap:.0%} of ground_truth_evidence.quote's significant words also appear in the rendered prompt")

    return PreflightResult(passed=not hard_failures, hard_failures=hard_failures, warnings=warnings)


def assert_no_leakage(rendered_prompt: str, row_raw: dict) -> PreflightResult:
    """Fail-closed helper: raises LeakagePreflightFailure on any hard failure instead of
    returning a result the caller might forget to check."""
    result = check_leakage(rendered_prompt, row_raw)
    if not result.passed:
        raise LeakagePreflightFailure("; ".join(result.hard_failures))
    return result


def main() -> int:
    from _module_loader import load_lib_module
    load_corpus = load_lib_module("01_load_corpus.py", "load_corpus")

    rows, _ = load_corpus.load_corpus()
    fail = 0
    for row in rows:
        rendered = str(load_corpus.model_facing_payload(row))
        result = check_leakage(rendered, row.raw)
        if not result.passed:
            fail = 1
            print(f"FAIL  {row.candidate_id}: {result.hard_failures}")
    if not fail:
        print(f"PASS  leakage preflight clean for all {len(rows)} rows' model_facing_input")
    return fail


if __name__ == "__main__":
    raise SystemExit(main())
