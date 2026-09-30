# Architecture Decisions

This document records significant technical and architectural decisions that should remain stable across tasks.

## Decision Format

Use the following format for each decision:

### ADR-NNN — Title

**Status:** Proposed

**Date:** YYYY-MM-DD

**Context**

<!-- What problem or decision needed to be addressed? -->

Not defined.

**Decision**

<!-- What was decided? -->

Not defined.

**Rationale**

<!-- Why was this decision chosen? -->

Not defined.

**Consequences**

<!-- What are the important positive and negative consequences? -->

Not defined.

**Alternatives Considered**

<!-- What reasonable alternatives were considered and why were they not chosen? -->

None documented.

## Recorded Decisions

### ADR-001 — Four-decision-type corpus taxonomy for Phase 4 System-1 evaluation

**Status:** Accepted

**Date:** 2026-09-30

**Context**

Phase 4 needed a bounded, real-evidence-only corpus (`laya/corpus/phase-4.1-decision-corpus.jsonl`)
to evaluate whether a cheap decision layer can assist specific workflow judgments. Evaluating
"can a model write good code" or an open-ended judgment set would conflate decision-routing
evaluation with coding-agent benchmarking (a `bench/`-level concern, not a Phase 4 one).

**Decision**

The corpus is scoped to exactly four decision types: `trivial_vs_staged`,
`documented_limitation_vs_defect`, `human_acceptance_required`, and
`agent_verification_applicable` — each a bounded, real-world workflow classification judgment
with a clean-or-borderline/inclusion-status label, never an open-ended coding task.

**Rationale**

These four map directly to routing decisions the Agentic OS actually needs to make during real
engineering work (is this trivial or does it need staged execution; is this a documented
limitation or a defect; does this change require human acceptance; is agent-level verification
even applicable). Keeping the taxonomy to exactly these four prevents Phase 4 from drifting into
evaluating general model capability instead of decision-routing capability.

**Consequences**

Positive: keeps Phase 4 scoped and comparable across adapters (Laya/DeepSeek/Claude all answer
the same four decision types). Negative: some partitions are very small (e.g. the
`system1_judgment` block of `agent_verification_applicable` is n=2 in every existing run, flagged
`sample_size_warning: true`) — any comparison drawn from this corpus must treat low-n partitions
as directional, not statistically decisive, until the corpus grows.

**Alternatives Considered**

An open-ended "can this model do useful engineering judgment" corpus was considered and rejected
as unbounded and not falsifiable in the same way.

---

### ADR-002 — Deterministic prefilter runs before any System-1/model call (DP-22)

**Status:** Accepted

**Date:** 2026-09-30

**Context**

Some `agent_verification_applicable` rows (tagged `DP-22` in `candidate_id`, e.g. `KC-DP22-01`)
are resolvable by a simple, deterministic rule (file-extension/path-keyword matching) without
needing any model inference at all.

**Decision**

`laya/harness/lib/04_deterministic_prefilter.py` (a versioned rule set, currently
`rule_version = "1.0"`, exposed as `model_identifier = "deterministic_prefilter_v1.0"`) runs on
every DP-22-eligible row before any adapter (Laya/DeepSeek/Claude) is invoked. Rows it resolves
are scored under a separate `deterministic_prefilter_validation` block in the aggregate report;
only rows it does not resolve reach a model at all, under the separate `system1_judgment` block.

**Rationale**

Directly implements the project's "deterministic tooling should be preferred when sufficient"
principle: it is real, measured token minimization with no correctness cost where the rule
applies (100% accuracy on its own partition in every run to date), and it keeps the model-facing
evaluation honest by never letting an easy, rule-resolvable row inflate a model's apparent
accuracy.

**Consequences**

Positive: cheaper evaluation, and a clean per-mechanism accuracy breakdown rather than one
blended number. Negative: the rule set itself needs its own versioning discipline
(`rule_version`) and its own correctness bar — a bug in the prefilter would silently
misclassify rows before any model ever sees them, so it is not exempt from the same scrutiny as
a model adapter.

**Alternatives Considered**

Sending every DP-22 row to a model regardless was rejected as unnecessary spend for a
class of rows that a simple, auditable rule already resolves correctly.

---

### ADR-003 — Strict structured-output parsing, no broad extraction from prose

**Status:** Accepted

**Date:** 2026-09-30

**Context**

A model's raw text response must be turned into a single decision value. A parser could either
strictly require the exact contracted shape (`{"decision": "<value>"}` and nothing else), or
attempt to recover a decision from looser/noisier output (e.g. by regex-scanning for a JSON
object anywhere in a longer response).

**Decision**

`deepseek_adapter.parse_decision_content` (shared by the DeepSeek and Claude adapters) requires
an exact `{"decision": "<value>"}` object with no extra keys and a value in
`allowed_output_values`; anything else is `malformed_output`/`invalid_output`, never repaired.
This is a fixed measurement policy, not a per-adapter convenience.

**Rationale**

Malformed output is itself evaluation signal: it measures a model's actual adherence to the
transport contract, not just its underlying judgment. Silently repairing malformed output would
hide a real capability/reliability difference between models behind an increasingly permissive
parser.

**Consequences**

Positive: comparable, auditable pass/fail semantics across all model adapters. Negative
(materialized): this policy is strict enough that a model's own default formatting habit
(Claude Haiku 4.5 wrapping its answer in a markdown code fence, see ADR-004 and ADR-006) can
produce a majority-invalid result set even when the model's underlying judgment is fine — a
narrow, whole-response fence-unwrap was added ahead of this parser specifically to keep the
strict-parsing/no-repair guarantee intact for genuinely malformed output while not
misclassifying "correct decision, wrapped in a fence the transport instruction asked it not to
use" as the same failure class. This is a narrowly scoped exception, not a loosening of the
policy: content outside a single whole-response fence is still rejected exactly as before.

**Alternatives Considered**

A permissive "find any JSON object in the text" extractor was considered and rejected — it
would blur the line between "the model answered correctly in a slightly wrong shape" and "the
model's output cannot be trusted at all," which this evaluation needs to keep distinct.

---

### ADR-004 — Adapter reuse strategy: shared parser code across providers

**Status:** Accepted

**Date:** 2026-09-30

**Context**

`claude_adapter.py` and `deepseek_adapter.py` both need to validate a model's raw text against
the same JSON transport contract (ADR-003). The logic could be duplicated per adapter or shared.

**Decision**

`claude_adapter.py` imports `parse_decision_content` and `JSON_TRANSPORT_INSTRUCTION_TEMPLATE`
directly from `deepseek_adapter.py` rather than duplicating them; `deepseek_adapter.py` itself is
never modified to accommodate Claude. Provider-specific behavior lives only in the adapter that
needs it — currently, `claude_adapter.py`'s `_unwrap_whole_response_markdown_fence()` runs before
handing text to the shared parser, because Claude Haiku 4.5 needed it and DeepSeek Flash did not.

**Rationale**

The parsing/validation logic is genuinely provider-neutral text/JSON logic with no
DeepSeek-specific content; sharing it is reuse, not premature abstraction, and avoids two
divergent implementations of the same contract silently drifting apart.

**Consequences**

Positive: one shared, well-tested parser to maintain; a fix or test added for one provider's
edge case doesn't need to be duplicated by hand for the other. Negative (materialized): reusing
code written and validated against one provider's real behavior does not guarantee it holds for
a second provider's real behavior — the markdown-fence gap was not caught by
`test_claude_adapter.py` before the historical Claude run because no test fixture simulated
Claude's actual default output shape, only idealized clean JSON. Any future adapter reuse should
include a fixture based on that new provider's actual observed output, not only the shared
contract's idealized shape.

**Alternatives Considered**

A fully separate parser per adapter was considered and rejected as needless duplication of
identical validation logic; it would not by itself have prevented this gap (the same untested
assumption could have been copy-pasted into a duplicate parser just as easily).

---

### ADR-005 — Deterministic prefilter and System-1 (model) judgment are scored as separate mechanisms, never blended

**Status:** Accepted

**Date:** 2026-09-30

**Context**

A single decision type (`agent_verification_applicable`) can be answered by two categorically
different mechanisms: a deterministic rule (ADR-002) or a genuine model judgment ("System-1").
The aggregate report needs to represent both without letting one mechanism's accuracy silently
inflate or dilute the other's.

**Decision**

`laya/harness/lib/07_aggregate_report.py` scores `deterministic_prefilter_validation` and
`system1_judgment` as separate named blocks within the same decision type's report, each with its
own `model_identifier`, `n`, `coverage`, and `accuracy` — never merged into one blended number for
`agent_verification_applicable`.

**Rationale**

Deterministic rule accuracy and model judgment accuracy are different claims about different
mechanisms; a reader (or a future Phase 4.8 comparison) needs to be able to ask "is the
*model*, specifically, reliable here" without a large, easy, rule-resolved partition masking a
small, hard, model-only partition's real performance (or vice versa).

**Consequences**

Positive: honest, mechanism-specific accuracy reporting. Negative: the `system1_judgment` block
is consequently very small in the current corpus (n=2, `sample_size_warning: true`) — the
separation makes this smallness visible rather than hiding it inside a larger blended number,
which is the intended effect but does mean the model-only signal from this partition should be
read as directional, not conclusive.

**Alternatives Considered**

A single blended accuracy figure per decision type was considered and rejected as it would
misrepresent model-specific reliability whenever the deterministic prefilter resolves most of
the rows for a given corpus.

---

### ADR-006 — Historical evaluation evidence policy: preserve, never silently reinterpret

**Status:** Accepted

**Date:** 2026-09-30

**Context**

Three runs exist under `laya/results/` (`phase4.5-laya-real-20260926T092215Z`,
`phase4-deepseek-flash-real-20260926T101940Z`, and
`phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z`), predating the current
4.5–4.8 plan being explicitly sequenced. The Claude run in particular has a known integration
defect (ADR-003/ADR-004): 24 of its 36 rows are `malformed_output: invalid_json` because of the
markdown-fence gap fixed in this checkpoint.

**Decision**

A historical evaluation run is never deleted, rewritten, or regenerated in place to "fix" it
after a harness/adapter defect is found. It is preserved exactly as originally produced and is
instead reclassified in documentation:

- `phase4.5-laya-real-20260926T092215Z` — valid Phase 4.5 evaluation evidence under current
  contracts (corpus hash, schema version, and prefilter/leakage-preflight rule versions all
  current).
- `phase4-deepseek-flash-real-20260926T101940Z` — valid comparative evidence under current
  contracts.
- `phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z` — **an integration/smoke-test
  run with a known parser defect (fixed in `claude_adapter.py` after this run was captured), not
  valid Phase 4.6 model-quality baseline evidence.** It demonstrates the request/response
  plumbing worked (real HTTP 200s, real token/latency data) but its per-row accuracy figures must
  not be cited as evidence of Claude Haiku 4.5's actual decision-routing capability.

**Rationale**

Silently deleting or regenerating a defective historical run would erase the evidence of the
defect itself and make the defect's discovery/fix unverifiable later. Reclassifying it in
documentation, while keeping the artifact byte-identical, preserves both the historical record
and the corrected understanding of what that record actually demonstrates.

**Consequences**

Positive: full auditability of what went wrong and when it was fixed. Negative: a reader of
`laya/results/` without this ADR could still mistake the historical Claude run for valid
baseline evidence — this ADR, and any future documentation referencing that run, must carry this
classification forward explicitly rather than assuming it is self-evident from the filename.

**Alternatives Considered**

Deleting the defective run and re-running Claude immediately was considered and rejected for
this checkpoint: re-running requires a live Anthropic API call, which is out of scope for this
foundation-closure checkpoint, and deleting historical evidence of a real defect (even a fixed
one) would itself be a reproducibility regression.

---

### ADR-007 — `eligible_for_binary_scoring` is authoritative for binary evaluation

**Status:** Accepted

**Date:** 2026-09-30

**Context**

The corpus schema (`laya/schema/decision_corpus_schema.json`) gives every row an
`eligible_for_binary_scoring` flag: false for every `trivial_vs_staged` row, false for
`include_as_borderline`/`exclude` rows generally, true only for clean `include` rows. The
harness never read this flag. The three `09_run_evaluation*.py` runners filtered only
`inclusion_status == "exclude"`, and `07_aggregate_report.py` scored whatever batch it was
given. As a result, all three 2026-09-26 aggregate reports count `include_as_borderline` rows
with `eligible_for_binary_scoring: false` toward accuracy (five such rows in the Laya run).
`trivial_vs_staged` was unaffected, because it was already never scored, by decision type.

Three concepts that the harness had conflated are distinct:

- **Corpus inclusion** (`inclusion_status`: `include` / `include_as_borderline` / `exclude`):
  whether a row belongs in the corpus as evaluation material. Borderline rows remain in the
  corpus, are sent to models, and have their predictions recorded.
- **Binary scoring eligibility** (`eligible_for_binary_scoring`): whether a row's ground truth
  is clean enough to count a prediction as correct or incorrect.
- **Mechanism partitioning** (DP-22 `corpus_partition`, DP-16 `evidence_polarity`): which
  scored block a row belongs to (ADR-002, ADR-005). This is independent of eligibility.

**Decision**

- `eligible_for_binary_scoring` is authoritative for binary evaluation. A row with the flag
  false, or missing, contributes nothing to any block's `n`, correctness counts, accuracy,
  coverage, or calibration. Instead it is listed in that block's
  `binary_scoring_ineligible_ids`. This is enforced once, in `07_aggregate_report._block`,
  which every scored block routes through.
- `inclusion_status == "exclude"` stays an independent inclusion concept and is also enforced
  there. It is not inferred from the eligibility flag.
- Partitioning, the DP-23 `normative_label` target, DP-11's not-scored status, and the rule
  that an invalid prediction is a coverage gap rather than an incorrect answer are all
  unchanged.
- The DP-22 `deterministic_prefilter_validation` block carries a `prefilter_routing` breakdown
  so a reader can separate the whole partition's rows (`partition_rows_total`), rows the rule
  resolved (`handled`), rows it left unresolved (`deferred`, `deferred_ids`), rows eligible for
  binary scoring (`binary_scoring_eligible`, equal to the block's `n`), and rows actually
  scored (`scored`). Deferred rows in this partition are not routed to System-1, because
  routing is by partition (ADR-002). Within the block, an eligible deferral counts toward
  `invalid_predictions` and lowers `coverage`; it never lowers `accuracy`.
- Historical aggregate reports are immutable evidence (ADR-006) and are not rewritten. Formal
  reports may be regenerated offline from preserved `predictions.jsonl` with
  `laya/harness/lib/10_rescore_offline.py`. That script writes a separate
  `<run_id>--rescore-eligible-only-v1/` directory whose manifest records the source artifact
  hashes, corpus hash, scoring policy, and scoring-module hashes.

**Rationale**

The flag was authored at corpus-construction time, before any prediction existed, precisely to
mark ground truth too weak for a binary score. Ignoring it let borderline labels move headline
accuracy. For the Laya run, DP-16 overall moves from 5/7 to 3/5, DP-23 from 5/12 to 3/10, and
DP-22 System-1 from 1/2 to 0/1. The predictions themselves do not depend on the scoring policy,
so no model rerun is needed.

**Consequences**

Positive: reported accuracy now matches the corpus contract, the policy is enforced at one
point, and the excluded rows are visible by ID. Negative: already-small blocks shrink further
(DP-22 System-1 and DP-16 `absence_based` become n=1). Any figure cited from an original
2026-09-26 `aggregate_report.json` is exclude-only and must be labelled as such.

**Alternatives Considered**

Keeping exclude-only scoring and documenting the flag as DP-11-only was rejected: it contradicts
the schema's own definition of the flag. Rewriting the historical reports in place was rejected
under ADR-006.

## Statuses

- **Proposed** — under consideration.
- **Accepted** — the current project decision.
- **Superseded** — replaced by a later decision.
- **Rejected** — considered but explicitly not chosen.

## Decision Rules

- Give each decision a unique ADR ID.
- Do not reuse ADR IDs.
- Record significant architectural or technical decisions.
- Include rationale, not just the outcome.
- Do not use this document as an activity log.
- Do not record trivial implementation choices.
- When a decision is superseded, keep the historical record and link or reference the replacing decision.
- Agents should follow accepted decisions unless a current user instruction explicitly requires reconsideration.
