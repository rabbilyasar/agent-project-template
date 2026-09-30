# Phase 4.1 decision corpus

Historical, real-evidence-only corpus for evaluating whether a cheap decision layer ("Laya")
could plausibly help with a small set of bounded workflow judgments, without becoming
authoritative over any existing deterministic check or human gate. This is a **data contract and
candidate-selection artifact only** — no Laya integration, no model evaluation, no scoring has
been run against it.

## Contents

- `corpus/phase-4.1-decision-corpus.jsonl` — 36 rows, one per mined historical candidate, across
  four decision types: `trivial_vs_staged`, `agent_verification_applicable`,
  `documented_limitation_vs_defect`, `human_acceptance_required`.
- `schema/decision_corpus_schema.json` — the row schema, documenting which fields are
  decision-time information (`decision_time_context`, `model_facing_input`) versus post-decision
  evidence (`ground_truth_evidence`, and for `human_acceptance_required`, `empirical_basis`).
- `validate_corpus.py` — deterministic, dependency-free validation (`python3 laya/validate_corpus.py`).
  Checks schema conformance, that every `model_facing_input` is derivable from
  `decision_time_context`, that no post-decision evidence leaks into the model-facing input,
  ID uniqueness, inclusion/scoring-eligibility consistency, the `human_acceptance_required`
  four-field normative/empirical structure, that `trivial_vs_staged` has no clean "trivial"
  example and is never scoring-eligible, `documented_limitation_vs_defect`'s evidence-polarity
  tagging, and `agent_verification_applicable`'s pre-filter/judgment partition separation.

## Known, deliberately unresolved limitations

Every row traces to a real, cited source (this repo's own three Phase 3 dogfood runs, or a mined
excerpt from a historical project's session log) — nothing here is synthetic. That means the
corpus is honestly uneven:

- `trivial_vs_staged` has real coverage for the "staged" class only; no clean "trivial" example
  exists in any source mined so far. No row of this type is scoring-eligible.
- `agent_verification_applicable` has only two genuinely ambiguous real examples (both from Zeus);
  the rest validate the deterministic file-path pre-filter and are kept in a separate
  `corpus_partition`, not mixed into judgment evaluation.
- `documented_limitation_vs_defect`'s `absence_based` evidence polarity has weaker real support
  than `positive_match` and must be reported separately, never merged into one accuracy figure.
- `human_acceptance_required` keeps `normative_label` (policy) and `empirical_label` (observed
  human behavior) as separate fields on every row — they are allowed to, and in several real rows
  do, disagree.
