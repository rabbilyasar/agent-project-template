#!/usr/bin/env python3
"""Shared leakage-detection primitives.

Used by both laya/validate_corpus.py (corpus-authoring-time checks on model_facing_input
as stored) and laya/harness/lib/02_leakage_preflight.py (evaluation-time checks on a
rendered prompt string, right before it would be sent to any model). One set of rules,
two call sites -- see AGENTS.md: do not duplicate existing mechanisms.

Two detection strategies, deliberately not the same strength:
- exact_copy_hits / label_token_hits: hard-fail signals (exact substring or a literal
  label token that matches the row's own answer). No broad keyword blacklist.
- paraphrase_overlap: a WARN-only heuristic (significant-word overlap ratio). Documented
  limitation: cannot detect a fully reworded paraphrase sharing no vocabulary, and can
  false-positive on ordinary shared domain vocabulary. Never a pass/fail signal.
"""
from __future__ import annotations

LABEL_TOKENS = [
    "trivial", "staged", "applicable", "not applicable", "deliberate", "defect",
    "sufficient without", "substantive engagement", "bare acknowledgment", "not available",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "is", "are",
    "was", "were", "this", "that", "it", "its", "as", "by", "at", "be", "not", "no", "but",
    "from", "into", "than", "then", "each", "any", "all", "has", "had", "have", "been",
}


def flatten_strings(obj):
    """Yield every string value nested anywhere inside obj (dict/list/str)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from flatten_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from flatten_strings(v)


def exact_copy_hits(haystack_blob: str, fields: dict) -> list[str]:
    """fields: {field_name: value_or_None}. Returns names whose value (len > 20) appears
    verbatim, case-insensitive, inside haystack_blob. Short values (<=20 chars) are skipped
    because they are too easily coincidental to count as proof of copying."""
    hits = []
    blob = haystack_blob.lower()
    for name, value in fields.items():
        if value and len(value) > 20 and value.lower() in blob:
            hits.append(name)
    return hits


def label_token_hits(haystack_blob: str, own_label_values: set[str], exempt: bool = False) -> list[str]:
    """own_label_values: this row's own label strings, already underscore->space and lowered.
    Returns LABEL_TOKENS entries that are both literally present in haystack_blob AND equal to
    one of this row's own labels -- avoids flagging unrelated rows' vocabulary overlapping by
    coincidence. `exempt` is set by callers for decision types whose input legitimately quotes
    label-adjacent vocabulary by design (documented_limitation_vs_defect's curated excerpt)."""
    if exempt:
        return []
    blob = haystack_blob.lower()
    return [tok for tok in LABEL_TOKENS if tok in blob and tok in own_label_values]


def significant_words(text: str) -> set[str]:
    return {
        w.strip(".,()-:;\"'").lower()
        for w in text.split()
        if len(w.strip(".,()-:;\"'")) > 3 and w.strip(".,()-:;\"'").lower() not in STOPWORDS
    }


def paraphrase_overlap(haystack_blob: str, source_text: str) -> float | None:
    """Returns the fraction of source_text's significant words that also appear in
    haystack_blob, or None if source_text has no significant words to compare."""
    src_words = significant_words(source_text)
    if not src_words:
        return None
    haystack_words = significant_words(haystack_blob)
    return len(src_words & haystack_words) / len(src_words)
