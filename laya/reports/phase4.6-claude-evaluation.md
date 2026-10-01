# Phase 4.6 — Claude Evaluation Report

Formal evaluation record for Phase 4.6. It is descriptive: it reports what the run measured
under the Phase 4.2 evaluation contracts and the ADR-007 eligible-only scoring policy. It makes
no adoption, ranking, routing or model-selection decision. The Laya comparison section is a
row-by-row statement of fact, not a verdict.

> **Historical record (ADR-008, 2026-10-01).** These figures were computed against the
> original corpus (`a3a5102a…`) under scoring policy `eligible_only_v1`. ADR-008 subsequently
> made AGENT-DP23-01 ineligible, leaving DP-23 with only one eligible ground-truth class.
> DP-23 is therefore now not scored. DP-11, DP-16, and DP-22 figures are unchanged. See the
> corrected-corpus v2 rescore artifact at
> `laya/results/phase4.6-claude-claude-haiku-4-5-20251001-real-20260930T165609Z--rescore-eligible-only-v2-corrected-corpus/`.
> The reproduction commands below describe the historical run and work only with the
> corresponding historical code revision.

**Result:** on this 16-row eligible scored subset of the Phase 4.1 corpus, Claude Haiku 4.5
produced 16/16 correct predictions under the Phase 4.2 evaluation contracts. This is not a
general accuracy figure, not a production accuracy figure, and not evidence that Claude is
universally better than Laya.

## Evidence

| Item | Value |
|---|---|
| Run (source of truth) | `laya/results/phase4.6-claude-claude-haiku-4-5-20251001-real-20260930T165609Z/` |
| Run window | 2026-09-30T16:56:09Z – 16:56:33Z |
| Harness commit (recorded in manifest) | `b9a6bb93838654329ea42e04b86f253fa453c44e`, `harness_uncommitted_changes: false` |
| Scoring policy | `eligible_only_v1` (ADR-007), committed evaluator `07_aggregate_report.py` |
| Corpus | `laya/corpus/phase-4.1-decision-corpus.jsonl`, SHA-256 `a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b` |
| `predictions.jsonl` SHA-256 | `d8f3afcf9a0f400be940d49ddd334de63e67a06467533854af17d7aaa611332e` (33 rows) |
| `aggregate_report.json` SHA-256 | `dec0d83ac1f1388f5beee770ff9f3c0d24acf0b3767f13b4d11d6591b4feef5a` |
| `manifest.json` SHA-256 | `e247ab00947fa738590a0b5fc1b5cf743adef52f83b97d8004efa10629d3c31b` |

Prompt contract SHA-256 hashes, as recorded in the manifest:

| Contract | SHA-256 |
|---|---|
| `agent_verification_applicable.json` | `580a6ccf20fe4951d05721cac0483ac060616ce976861aaeb2b73a7d4c8d6481` |
| `documented_limitation_vs_defect.json` | `20c7d7fdc60c8ce427ec4c709d19dafd19f2bae9015b3d8ee6ffe54d8194d0f4` |
| `human_acceptance_required.json` | `96a2c3da58cd92a2b056069db35f73b632c88f967c6065bda4abc371f37f4a64` |
| `trivial_vs_staged.json` | `9ce0af5c934f620dd5cb31d2d511643fc270c2a87353d6adf74c20a399a2676e` |

The historical Claude smoke-test run
(`phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z`) is unchanged. It remains
integration/smoke-test evidence only (ADR-006), and no figure in this report comes from it.

## What was evaluated

- **Model:** `claude:claude-haiku-4-5-20251001:direct-api`. This is the model the repository's
  Claude adapter and runner already define, so it was not a new experimental variable.
- **API settings:** Anthropic Messages API `2023-06-01`, `max_tokens: 64`, `temperature` not
  set (the API default applies), no thinking, no tools, no structured-output parameter.
- **Prompt:** each request carried only the prompt contract's `decision_question` and the shared
  JSON transport instruction as the system prompt, plus the row's `model_facing_input` as the
  user message. No repository context, other rows or earlier outputs were sent.
- **Parsing:** strict JSON parsing, after unwrapping a markdown fence only when it encloses the
  whole response (ADR-003, ADR-004). Anything else is recorded as invalid and never repaired.
- **Calls:** 26, one per row, with no retries and no other model calls. All 26 returned HTTP
  200, each with a distinct message ID, from `claude-haiku-4-5-20251001` on the standard
  service tier.

## Row selection and routing

Pipeline: corpus load → leakage preflight (all 36 rows passed) → DP-22 deterministic prefilter
→ routing by partition → Claude → canonical results → committed scorer and aggregator.

| Rows | Count | Handling |
|---|---|---|
| DP-22 `system1_judgment` (ZEUS-DP22-02, ZEUS-DP22-03) | 2 | sent to Claude |
| DP-11, DP-16 and DP-23 rows not marked `exclude` | 24 | sent to Claude, borderline rows included |
| Excluded non-DP-22 rows (AGENT-DP11-01, JOSS-DP11-01, ZEUS-DP16-02) | 3 | not sent; listed in the manifest's `skipped_excluded_candidate_ids`; absent from `predictions.jsonl` |
| DP-22 prefilter partition plus excluded RP-DP22-01 | 7 | resolved by `deterministic_prefilter_v1.0`, never sent to Claude |

**DP-22 prefilter routing:** the 7 prefilter results are identical to Phase 4.5 in prediction,
validity, error, model identifier and raw rule output.
- The prefilter partition has 6 rows: 4 handled and 2 deferred (KRIY-DP22-02, ZEUS-DP22-01).
- The deferred rows are not routed to System-1 (ADR-002), so they get no decision from any
  mechanism.
- The prefilter block's `n=5` is those 6 rows minus ineligible ZEUS-DP22-01. Its coverage is
  4 of 5.

## Results (eligible-only, authoritative)

| Block | Mechanism | Eligible `n` | Valid | Correct | Coverage | Ineligible rows (not scored) |
|---|---|---|---|---|---|---|
| DP-22 `deterministic_prefilter_validation` | prefilter v1.0 | 5 | 4 | 4 | 4/5 | ZEUS-DP22-01 |
| DP-22 `system1_judgment` | Claude | 1 | 1 | 1 | 1/1 | ZEUS-DP22-02 |
| DP-16 overall | Claude | 5 | 5 | 5 | 5/5 | ENV-DP16-03, JOSS-DP16-01 |
| DP-16 `positive_match` | Claude | 4 | 4 | 4 | 4/4 | ENV-DP16-03 |
| DP-16 `absence_based` | Claude | 1 | 1 | 1 | 1/1 | JOSS-DP16-01 |
| DP-23 (`normative_label`) | Claude | 10 | 10 | 10 | 10/10 | JOSS-DP23-05, KC-DP23-01 |
| DP-11 | Claude | — | 5 of 5 | not scored | 5/5 | whole type, by contract |

The eligible scored System-1 decisions total 16/16: DP-22 System-1 1/1, DP-16 5/5, and DP-23
10/10. The `system1_judgment` block carries `sample_size_warning: true`.

### Eligible scored rows

| Row | Type | Target field | Label | Claude | Correct |
|---|---|---|---|---|---|
| ZEUS-DP22-03 | DP-22 | `ground_truth_label` | applicable | applicable | yes |
| KC-DP16-01 | DP-16 (positive_match) | `ground_truth_label` | deliberate | deliberate | yes |
| ENV-DP16-01a | DP-16 (positive_match) | `ground_truth_label` | deliberate | deliberate | yes |
| ENV-DP16-02 | DP-16 (positive_match) | `ground_truth_label` | deliberate | deliberate | yes |
| ZEUS-DP16-01 | DP-16 (positive_match) | `ground_truth_label` | defect | defect | yes |
| ENV-DP16-01b | DP-16 (absence_based) | `ground_truth_label` | defect | defect | yes |
| AGENT-DP23-01 | DP-23 | `normative_label` | sufficient_without | sufficient_without | yes |
| JOSS-DP23-01, JOSS-DP23-02, JOSS-DP23-03, JOSS-DP23-04, KRIY-DP23-01, KRIY-DP23-02, RP-DP23-01, RP-DP23-02, RP-DP23-03 | DP-23 | `normative_label` | required | required | yes (9 rows) |

All 16 rows are `include`, `eligible_for_binary_scoring: true` and valid.

Among the 10 eligible scored DP-23 rows, `normative_label` is 9 `required` and 1
`sufficient_without` (11:1 across all 12 DP-23 corpus rows).

### Validity

- **Counts:** 25 of 26 Claude responses are valid.
- **The one invalid response:** ZEUS-DP22-02 (`malformed_output: invalid_json`,
  `stop_reason: max_tokens`). It is a whole-response fenced JSON answer followed by
  explanatory prose, cut off at the 64-token limit. It is stored verbatim in `raw_response` and
  not repaired.
- **Effect on scoring:** none. ZEUS-DP22-02 is `include_as_borderline` and ineligible, so it is
  outside every scored block.
- **Response shapes:** 24 responses were a whole-response markdown fence (unwrapped by the
  adapter) and 2 were bare JSON.
- **DP-11:** 5 valid predictions (4 `staged`, 1 `trivial`), recorded for qualitative review
  only. No accuracy is computed.

### Cost and latency

| Group | Calls | Input tokens (min–max) | Output tokens |
|---|---|---|---|
| DP-22 System-1 | 2 | 450 (208–242) | 78 |
| DP-11 | 5 | 748 (124–216) | 71 |
| DP-16 | 7 | 1,415 (180–224) | 100 |
| DP-23 | 12 | 1,738 (130–171) | 165 |
| **Total** | **26** | **4,351** | **414** |

- **Caching:** cache read and cache write tokens were 0 on every call. No caching was
  configured.
- **Output tokens:** 9–16 on 25 calls, and 64 on the one call that hit `max_tokens`.
- **Latency:** measured per call, 698–2,668 ms, with a mean of 935.6 ms and a median of
  824.1 ms. This is client-side wall-clock time for one HTTP request, not model latency alone.
- **Cost:** an estimated $0.0064, at $1.00 / $5.00 per million input/output tokens (first-party
  list price for Haiku 4.5).
- **Same prompts as the smoke test:** every row's input token count equals the historical smoke
  run's count for the same row.

### Confidence and calibration

Unavailable by contract. The adapter reports no confidence or probability distribution for
Claude, so `calibration.available` is false in every block. No calibration figure exists for
this run.

## Leakage

- **Hard preflight:** passed for all 36 rows before any request. A literal label-token check on
  the 16 eligible rows' inputs found no matches.
- **Heuristic warnings:** the validator's paraphrase heuristic still flags ENV-DP16-03,
  JOSS-DP23-05 and RP-DP23-03 for human review. These are heuristic signals, not confirmed
  leakage.
- **Effect on the scored rows:** ENV-DP16-03 and JOSS-DP23-05 are ineligible and not scored.
  RP-DP23-03 is eligible and scored; Claude's prediction for it is correct.

## Factual comparison with the Phase 4.5 Laya predictions

Claude and Laya differed on 11 of the 26 rows both models were asked to answer. Ten differences
occurred among the 16 eligible scored rows. The remaining difference was ZEUS-DP22-02, an
ineligible row where Claude produced no valid prediction and Laya predicted `applicable`.

| Row | Label | Laya (Phase 4.5) | Claude (Phase 4.6) |
|---|---|---|---|
| ZEUS-DP22-02 (ineligible) | applicable | applicable | no valid prediction |
| ZEUS-DP22-03 | applicable | not_applicable | applicable |
| ENV-DP16-01b | defect | deliberate | defect |
| ENV-DP16-02 | deliberate | defect | deliberate |
| JOSS-DP23-02, JOSS-DP23-03, KRIY-DP23-01, KRIY-DP23-02, RP-DP23-01, RP-DP23-02, RP-DP23-03 | required | sufficient_without | required |

On the other 15 rows the two predictions are identical. That is 6 eligible rows (KC-DP16-01,
ENV-DP16-01a, ZEUS-DP16-01, AGENT-DP23-01, JOSS-DP23-01, JOSS-DP23-04) and 9 ineligible ones.

The two systems ran under different transports and output mechanisms: a local classifier head
versus a hosted LLM returning JSON. They also ran on different dates, and each produced a
single response per row. This section records the differences and draws no conclusion from
them.

## Limitations

- **Sample size:** there are 16 eligible scored decisions in total. DP-22 System-1 and DP-16
  `absence_based` are each n=1, so each is a single observation.
- **DP-23 class balance:** the eligible subset is 9:1, so it allows almost no statement about
  the `sufficient_without` class.
- **Single sample:** one response per row at the API's default temperature. Repeatability was
  not measured.
- **No calibration:** no confidence information is available.
- **Leakage review:** RP-DP23-03 carries a heuristic leakage warning, although it passed the
  hard leakage preflight. No human review of the heuristic warnings has been recorded.
- **Prefilter gap:** two DP-22 prefilter-partition rows (KRIY-DP22-02, ZEUS-DP22-01) receive no
  decision from any mechanism under the current routing.
- **Output limit:** the 64-token limit, together with the model adding prose after the answer,
  produced one invalid response. The limit was kept, as specified for the controlled run.
- **Scope:** no claim of generalization beyond this corpus, of production readiness, or of
  superiority over any other system.

## Reproduction

These commands reproduce the historical record at commit `55e8968` (or any later revision before
`6299603`, which still contains the original corpus). From `6299603` onward, the corpus hash
differs (ADR-008), and `10_rescore_offline.py` aborts at its corpus-hash check.

These commands need no model or network:

```sh
bash laya/harness/tests/run_all.sh        # deterministic harness self-tests
python3 laya/validate_corpus.py           # corpus contract validation
sha256sum laya/corpus/phase-4.1-decision-corpus.jsonl laya/results/phase4.6-claude-claude-haiku-4-5-20251001-real-20260930T165609Z/*
python3 laya/harness/lib/09_run_evaluation_claude.py --plan-only   # preflight + planned 26 calls; needs credentials present, makes no request
```

The aggregate can be recomputed offline from `predictions.jsonl` with the committed evaluator.
The `build_reports` command reproduces the historical aggregate at commit `55e8968`.
