# Phase 4 — DeepSeek Evaluation Report (historical run, eligible-only rescore)

Formal record of the historical Phase 4 DeepSeek run, rescored offline under the ADR-007
eligible-only policy. It is descriptive only: it contains no ranking and no adoption, routing or
model-selection decision. No DeepSeek or other API call was made to produce it.

**Result:** under the ADR-007 eligible-only scoring policy, DeepSeek produced 14/16 correct
predictions on the 16 eligible scored System-1 decisions in this historical Phase 4 evaluation.
This is not a general accuracy figure and not a production accuracy figure.

## Evidence

| Item | Value |
|---|---|
| Source run (immutable, ADR-006) | `laya/results/phase4-deepseek-flash-real-20260926T101940Z/` |
| Source run window | 2026-09-26T10:19:40Z – 10:19:59Z |
| Formal aggregate (authoritative) | `laya/results/phase4-deepseek-flash-real-20260926T101940Z--rescore-eligible-only-v1/aggregate_report.json` |
| Scoring policy | `eligible_only_v1` (ADR-007): `eligible_for_binary_scoring == true` and `inclusion_status != exclude` |
| Rescore code | commit `55e8968df922d9efda18b0edb015c19034a912db`, `harness_uncommitted_changes: false` |
| Corpus | `laya/corpus/phase-4.1-decision-corpus.jsonl`, SHA-256 `a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b` |
| Source `predictions.jsonl` SHA-256 | `23750786f62f9e38d72d5da6f3be755e45b274f1a7b07128b71d66a2dba32916` (36 rows) |
| Source `manifest.json` SHA-256 | `a6c45f8865d62da7d196880cd344593988907380cc77cc9f4c741608a56646b9` |
| Source `aggregate_report.json` SHA-256 | `e906b5a6db535ffd14038d5bac846e77ba742ab1be6e29f7433b9d81eeb6644f` (exclude-only, superseded) |
| Formal `aggregate_report.json` SHA-256 | `4d8b30a329ca3d9533ab2dca558dda6f4fcdc57a781c8d7c7cffc06af268c541` |

The formal aggregate was produced by `10_rescore_offline.py` from the preserved predictions,
with no network interfaces available and no model or network module loaded. Its manifest records
the source file hashes, `model_inference_performed: false` and
`source_artifacts_modified: false`. The historical DeepSeek artifacts remain byte-identical.

## What was evaluated

- **Model:** `deepseek:deepseek-flash:thinking-disabled:effort-none`. The raw responses report
  model `deepseek-flash` and a single `system_fingerprint`, `aeb56401ca74e127821c4f9126dcb669`.
- **Request settings:** OpenAI-compatible chat completions with
  `response_format: {"type": "json_object"}`, `thinking: {"type": "disabled"}`,
  `reasoning_effort: "none"`, no `max_tokens`, and no temperature set (provider default).
- **Prompt:** the system prompt is the contract's `decision_question` plus the shared JSON
  transport instruction. The user message is the row's `model_facing_input`.
- **Parsing:** the shared strict parser (ADR-003). Replaying it today reproduces all 29 recorded
  predictions and errors.
- **Calls:** 29, one per non-prefilter row, all HTTP 200 with `finish_reason: stop`. All 29
  responses are valid bare JSON.
- **Prefilter rows:** 7 rows were resolved by `deterministic_prefilter_v1.0`. Re-running the
  current rule reproduces all 7, and they are identical to the Phase 4.5 prefilter results.
- **Leakage:** the current hard leakage preflight passes for all 36 corpus rows.

## DP-22 routing

- **Prefilter partition:** 6 rows. 4 were handled; 2 were deferred (KRIY-DP22-02, ZEUS-DP22-01)
  and not routed to System-1 (ADR-002).
- **System-1 partition:** ZEUS-DP22-02 and ZEUS-DP22-03 were sent to DeepSeek.
- **Excluded row:** RP-DP22-01 was resolved by the prefilter and belongs to no scored block.
- **Prefilter block:** `n=5` (the 6 partition rows minus ineligible ZEUS-DP22-01); coverage
  4/5.

## Results (eligible-only, authoritative)

| Block | Mechanism | Eligible `n` | Valid | Correct | Coverage | Ineligible rows (not scored) |
|---|---|---|---|---|---|---|
| DP-22 `deterministic_prefilter_validation` | prefilter v1.0 | 5 | 4 | 4 | 4/5 | ZEUS-DP22-01 |
| DP-22 `system1_judgment` | DeepSeek | 1 | 1 | 1 | 1/1 | ZEUS-DP22-02 |
| DP-16 overall | DeepSeek | 5 | 5 | 5 | 5/5 | ENV-DP16-03, JOSS-DP16-01, ZEUS-DP16-02 (`exclude`) |
| DP-16 `positive_match` | DeepSeek | 4 | 4 | 4 | 4/4 | ENV-DP16-03 |
| DP-16 `absence_based` | DeepSeek | 1 | 1 | 1 | 1/1 | JOSS-DP16-01 |
| DP-23 (`normative_label`) | DeepSeek | 10 | 10 | 8 | 10/10 | JOSS-DP23-05, KC-DP23-01 |
| DP-11 | DeepSeek | — | 7 of 7 | not scored | — | whole type, by contract |

- **Eligible scored System-1 decisions:** 16, of which 14 are correct.
- **DP-23 errors:** the two eligible errors are JOSS-DP23-01 and JOSS-DP23-03. Both are labelled
  `required` and were predicted `sufficient_without`. Among the 10 eligible scored DP-23 rows,
  `normative_label` is 9 `required` and 1 `sufficient_without` (11:1 across all 12 DP-23 corpus
  rows).
- **DP-11:** all 7 predictions are `staged`. They are recorded for qualitative review only.
- **Validity:** there are no invalid DeepSeek predictions.
- **Sample size:** the `system1_judgment` block carries `sample_size_warning: true`.

### Cost and latency

| Group | Input tokens, mean (min–max) | Output tokens, mean | Latency ms, mean (min–max) |
|---|---|---|---|
| DP-22 System-1 (eligible) | 217 | 7.0 | 588.7 |
| DP-16 overall (eligible) | 216.2 (198–233) | 7.6 | 689.6 (543–851) |
| DP-23 (eligible) | 160.2 (146–185) | 6.9 | 636.8 (467–778) |

- **Totals over all 29 DeepSeek calls:** 5,237 input tokens, 204 output tokens, and per-call
  latency of 467–900 ms.
- **Caching:** 0 cache-hit tokens. `cache_write_tokens` is null because DeepSeek reports no such
  field.

## Historical-vs-current scoring reconciliation

The historical `aggregate_report.json` was produced under the pre-ADR-007 exclude-only policy. It
is kept byte-identical as historical evidence (ADR-006). Recomputing it with that policy
reproduces it exactly, apart from fields that were added later. Every difference below is
therefore caused by ADR-007 alone.

| Block | Historical (exclude-only, superseded) | Eligible-only (authoritative) | Rows that account for the difference |
|---|---|---|---|
| DP-22 prefilter | n=6, 4/4 valid, coverage 4/6 | n=5, 4/4 valid, coverage 4/5 | ZEUS-DP22-01 (deferred, ineligible) |
| DP-22 System-1 | 2/2 | 1/1 | ZEUS-DP22-02 (correct, ineligible) |
| DP-16 overall | 7/7 | 5/5 | ENV-DP16-03, JOSS-DP16-01 (both correct, ineligible) |
| DP-16 `positive_match` | 5/5 | 4/4 | ENV-DP16-03 |
| DP-16 `absence_based` | 2/2 | 1/1 | JOSS-DP16-01 |
| DP-23 | 10/12 | 8/10 | KC-DP23-01, JOSS-DP23-05 (both correct, ineligible) |

The excluded rows were never counted under either policy. ZEUS-DP16-02 has no label and was
filtered out by the historical runner; AGENT-DP11-01 and JOSS-DP11-01 are DP-11, which is never
scored.

## Comparison qualifications

These apply whenever this run is set beside the Phase 4.5 Laya or Phase 4.6 Claude evaluations.
**They do not prevent an offline comparison on the same corpus and scoring policy, but they limit
what can be inferred from differences between providers.**

- **Provenance:** the historical manifest has no harness commit, clean-tree flag or
  prompt-contract hashes. The available provenance is file timestamps and byte identity: the
  adapter, runner and prompt files were last modified before the run, and they are
  byte-identical to their committed versions.
- **Transport and output settings differ:**
  - DeepSeek used `response_format=json_object`, thinking disabled, effort `none` and no
    `max_tokens`.
  - Claude used instruction-only JSON with `max_tokens=64`.
  - Laya uses classifier heads.
- **Row set:** DeepSeek answered the 3 excluded rows (AGENT-DP11-01, JOSS-DP11-01,
  ZEUS-DP16-02), because this run predates the later rule that skips them. This has no effect on
  scoring.
- **Model pinning:** `deepseek-flash` is an alias, not a dated model snapshot. The
  `system_fingerprint` is preserved in every raw response.
- **Tokens:** tokenizers are provider-specific, so token counts should not be compared directly
  across providers.
- **Sampling:** one response per row, with default sampling. The runs were made on different
  dates.
- **Confidence:** no confidence or calibration information is available.

## Limitations

- **Sample size:** 16 eligible scored decisions in total. DP-22 System-1 and DP-16
  `absence_based` are each n=1.
- **DP-23 class balance:** 9:1 in the eligible subset.
- **Leakage review:** the validator's heuristic paraphrase warnings (ENV-DP16-03, JOSS-DP23-05,
  RP-DP23-03) remain unreviewed. Only RP-DP23-03 is scored; DeepSeek's prediction for it is
  correct.
- **Prefilter gap:** two DP-22 prefilter-partition rows receive no decision from any mechanism.
- **Scope:** no claim of generalization beyond this corpus or of production readiness.

## Reproduction

These commands need no model or network:

```sh
bash laya/harness/tests/run_all.sh
python3 laya/validate_corpus.py
sha256sum laya/corpus/phase-4.1-decision-corpus.jsonl laya/results/phase4-deepseek-flash-real-20260926T101940Z/*
python3 laya/harness/lib/10_rescore_offline.py laya/results/phase4-deepseek-flash-real-20260926T101940Z
sha256sum laya/results/phase4-deepseek-flash-real-20260926T101940Z--rescore-eligible-only-v1/aggregate_report.json
```

The last command should print the formal aggregate hash given under Evidence. Re-running the
rescore rewrites the derived `manifest.json`, which updates `generated_at` and records the
then-current `HEAD`.
