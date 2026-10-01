# Phase 4.5 — Laya Evaluation Report

Formal evaluation record for Phase 4.5. It is descriptive: it reports what the preserved evidence
measures, not whether Laya should be adopted. It contains no ranking against other models and
makes no Phase 4.8 decision.

> **Historical record (ADR-008, 2026-10-01).** These figures were computed against the
> original corpus (`a3a5102a…`) under scoring policy `eligible_only_v1`. ADR-008 subsequently
> made AGENT-DP23-01 ineligible, leaving DP-23 with only one eligible ground-truth class.
> DP-23 is therefore now not scored. DP-11, DP-16, and DP-22 figures are unchanged. See the
> corrected-corpus v2 rescore artifact at
> `laya/results/phase4.5-laya-real-20260926T092215Z--rescore-eligible-only-v2-corrected-corpus/`.
> The reproduction commands below describe the historical run and work only with the
> corresponding historical code revision.

## Evidence

| Item | Value |
|---|---|
| Source run (immutable, ADR-006) | `laya/results/phase4.5-laya-real-20260926T092215Z/` |
| Formal aggregate (authoritative) | `laya/results/phase4.5-laya-real-20260926T092215Z--rescore-eligible-only-v1/aggregate_report.json` |
| Scoring policy | `eligible_only_v1` (ADR-007) |
| Scoring code | commit `65e99aa9856e8934e02483ab780b1521aabb607b`, no uncommitted harness changes |
| Corpus | `laya/corpus/phase-4.1-decision-corpus.jsonl`, SHA-256 `a3a5102aee5a948fed6aee86c3cd3c8a6c392bf70f7b5d34ab3795073a2c1a2b` |
| Source `predictions.jsonl` SHA-256 | `69a4f174b5149d2bb90f756a98cacb376599c913afaed6e2674f1bd49ef13020` |
| Source `manifest.json` SHA-256 | `1899e689a5e4ea5df094c20a59bae803d54f2e22c15d765dc00e152aa67288dd` |
| Source `aggregate_report.json` SHA-256 | `ad58df67d9e05e76fe5e3393f8802df8c78e2aa33d8f154402f61466f10ee33b` (exclude-only, superseded) |
| Formal `aggregate_report.json` SHA-256 | `8f11b5936cc7fc0d7e0df3a53f7d5139c84e500cce04e369b0fd77ec60d91d33` |

The formal aggregate was produced offline from the preserved predictions. No model inference
occurred after the original run on 2026-09-26.

## What was evaluated

- **System:** `laya:0.3.20:convaiinnovations/laya-typed-decisions` (Laya 0.3.20). It ran on
  device `cuda` (PyTorch 2.14.0+rocm7.2, HIP 7.2, AMD Radeon RX 9070), unbatched and without
  accelerate.
- **Corpus:** all 36 rows of the Phase 4.1 corpus, across four decision types. Every one is a
  two-value choice:

  | ID | `decision_type` | Allowed values | Rows |
  |---|---|---|---|
  | DP-11 | `trivial_vs_staged` | `trivial`, `staged` | 7 |
  | DP-16 | `documented_limitation_vs_defect` | `deliberate`, `defect` | 8 |
  | DP-22 | `agent_verification_applicable` | `applicable`, `not_applicable` | 9 |
  | DP-23 | `human_acceptance_required` | `required`, `sufficient_without` | 12 |

- **Who answered what:** Laya answered 29 rows. The deterministic prefilter
  (`deterministic_prefilter_v1.0`, rule version 1.0) answered or deferred the other 7, all of
  them DP-22 rows.

## Method and terms

Pipeline: corpus load → leakage preflight (every row, before any model call) → DP-22
deterministic prefilter → routing by partition → Laya → canonical results → scoring and
aggregation.

This report keeps six concepts distinct:

- **Partition membership:** the corpus-assigned block a row belongs to. For DP-22 this is
  `corpus_partition`; for DP-16 it is `evidence_polarity`. Blocks are never merged (ADR-005).
- **Prefilter handling:** whether the frozen DP-22 rule resolved a row (*handled*) or not
  (*deferred*).
- **Eligibility:** `eligible_for_binary_scoring` in the corpus. Only rows that are eligible and
  not `exclude` count toward any correctness figure (ADR-007). Ineligible rows stay in the
  corpus, and their predictions are recorded. Each block lists them in
  `binary_scoring_ineligible_ids`.
- **Coverage:** valid predictions ÷ eligible rows in the block.
- **Correctness:** correct ÷ valid predictions. An invalid prediction or a deferral lowers
  coverage and is never counted as incorrect.
- **System-1 evaluation:** a model judgment on rows the prefilter is not meant to resolve. Here
  that means the DP-22 `system1_judgment` partition plus all DP-11, DP-16 and DP-23 rows.

Scoring targets: DP-16 and DP-22 are scored against `ground_truth_label`. DP-23 is scored only
against `normative_label`, never `empirical_label`. DP-11 is never scored for accuracy.

## DP-22 routing breakdown

| Row | `corpus_partition` | `inclusion_status` | Eligible | Prefilter | Answered by | Result in the formal aggregate |
|---|---|---|---|---|---|---|
| KC-DP22-01 | deterministic_prefilter_validation | include | yes | handled | prefilter | scored, correct |
| JOSS-DP22-01 | deterministic_prefilter_validation | include | yes | handled | prefilter | scored, correct |
| KRIY-DP22-01 | deterministic_prefilter_validation | include | yes | handled | prefilter | scored, correct |
| RP-DP22-02 | deterministic_prefilter_validation | include | yes | handled | prefilter | scored, correct |
| KRIY-DP22-02 | deterministic_prefilter_validation | include | yes | deferred | nothing | counted in `n`, invalid, lowers coverage |
| ZEUS-DP22-01 | deterministic_prefilter_validation | include_as_borderline | no | deferred | nothing | listed as ineligible, not in `n` |
| ZEUS-DP22-02 | system1_judgment | include_as_borderline | no | not handled | Laya | listed as ineligible, not in `n` |
| ZEUS-DP22-03 | system1_judgment | include | yes | not handled | Laya | scored, incorrect |
| RP-DP22-01 | none | exclude | no | handled | prefilter (recorded) | in no block |

**Deferred prefilter rows are not routed to System-1.** Routing is by partition (ADR-002), not
by deferral. So the two deferred rows in the prefilter partition, KRIY-DP22-02 and ZEUS-DP22-01,
received no decision from any mechanism.

The prefilter block's `prefilter_routing` field records this: 6 rows in the partition,
4 handled, 2 deferred, `deferred_routed_to_system1: false`, 5 eligible, 4 scored. The block's
`n=5` is the 6 partition rows minus ineligible ZEUS-DP22-01. Its coverage of 0.80 is 4 valid out
of 5 eligible, reduced by the eligible deferral KRIY-DP22-02.

## Results (eligible-only, authoritative)

| Block | Mechanism | Eligible `n` | Valid | Correct | Accuracy | Coverage | Ineligible rows (not scored) |
|---|---|---|---|---|---|---|---|
| DP-22 `deterministic_prefilter_validation` | prefilter v1.0 | 5 | 4 | 4 | 1.00 | 0.80 | ZEUS-DP22-01 |
| DP-22 `system1_judgment` | Laya | 1 | 1 | 0 | 0.00 | 1.00 | ZEUS-DP22-02 |
| DP-16 overall | Laya | 5 | 5 | 3 | 0.60 | 1.00 | ENV-DP16-03, JOSS-DP16-01, ZEUS-DP16-02 (`exclude`) |
| DP-16 `positive_match` | Laya | 4 | 4 | 3 | 0.75 | 1.00 | ENV-DP16-03 |
| DP-16 `absence_based` | Laya | 1 | 1 | 0 | 0.00 | 1.00 | JOSS-DP16-01 |
| DP-23 (`normative_label`) | Laya | 10 | 10 | 3 | 0.30 | 1.00 | JOSS-DP23-05, KC-DP23-01 |
| DP-11 | Laya | — | 7 of 7 | not scored | not scored | 1.00 | whole type, by contract |

The `system1_judgment` block carries `sample_size_warning: true`. All 29 Laya predictions are
valid against their output contract, with `error: null`. That is contract adherence, not decision
correctness.

### Per-type detail

- **DP-22 System-1:** the one eligible row, ZEUS-DP22-03, has label `applicable`. Laya predicted
  `not_applicable` with answer confidence 0.5359.
- **DP-16:**

  | Row | Polarity | Label | Laya | Confidence |
  |---|---|---|---|---|
  | ENV-DP16-01a | positive_match | deliberate | deliberate | 0.6937 |
  | KC-DP16-01 | positive_match | deliberate | deliberate | 0.5102 |
  | ENV-DP16-02 | positive_match | deliberate | defect | 0.7117 |
  | ZEUS-DP16-01 | positive_match | defect | defect | 0.7329 |
  | ENV-DP16-01b | absence_based | defect | deliberate | 0.5205 |

  Of the two errors, one is `deliberate` predicted as `defect` and one is `defect` predicted as
  `deliberate`.

- **DP-23:**
  - Among the eligible rows, the labels are 9 `required` and 1 `sufficient_without`. Laya's
    predictions are 2 `required` and 8 `sufficient_without`.
  - On the 9 `required` rows, 2 were predicted `required` and 7 `sufficient_without`. The
    1 `sufficient_without` row (AGENT-DP23-01) was predicted `sufficient_without`.
  - Answer confidences range from 0.5023 to 0.6863.
  - The contract asks whether "the nature of the change require[s] a human to personally inspect
    or use the result before it can be considered accepted … or is automated/agent verification
    sufficient on its own". This report states only the label and prediction distribution
    against that contract.

- **DP-11:** there are 7 valid predictions (6 `staged`, 1 `trivial`), recorded for qualitative
  review only. No DP-11 row is eligible for binary scoring, because the corpus has no clean
  `trivial` example. No accuracy is computed.

### Cost and latency

| Block | Input tokens, mean (min–max) | Output tokens |
|---|---|---|
| DP-16 overall | 172.2 (155–191) | 0 |
| DP-23 | 117.5 (102–143) | 0 |
| DP-22 System-1 | 177 | 0 |
| DP-22 prefilter | not applicable (no model) | — |

- **Per-row latency:** unavailable. The adapter records only batch-level `batch_elapsed_ms` in
  `raw_response` and deliberately does not divide it per row.
- **Batch timings:** four batches, at about 49 ms, 55 ms, 58 ms and 1503 ms. These are not
  per-decision latencies.
- **Wall clock:** the whole run took about 1.67 s, from 09:22:20.19Z to 09:22:21.86Z.

## Calibration and confidence

Confidence is Laya's `answer_confidence`: the probability assigned to the predicted value. It is
never Laya's entropy-based `confidence`. Expected calibration error (ECE) uses 10 equal-width bins.

| Block | Pairs | ECE |
|---|---|---|
| DP-16 overall | 5 | 0.1563 |
| DP-16 `positive_match` | 4 | 0.3102 |
| DP-16 `absence_based` | 1 | 0.5205 |
| DP-23 | 10 | 0.2712 |
| DP-22 System-1 | 1 | 0.5359 |

With 10 or fewer pairs per block, these ECE values are unstable. At n=1, ECE is simply the
distance between one confidence and one outcome.

**Checkpoint temperature warning:** at load time Laya emitted the warning recorded in the run
manifest: `laya: this checkpoint ships invalid temperatures or values outside [0.5, 5]; using
choice:11+=0.10058280825614929 -> 0.5. Treat confidence from the affected entries as
uncalibrated.` The checkpoint therefore ran with a clamped temperature instead of its shipped
value. The run records no per-prediction indication of which temperature entry applied. This
evaluation does not establish that Laya's confidences are calibrated, and none of the confidence
values above should be read as calibrated probabilities.

## Leakage

- **Hard preflight:** passed for all 36 rows before any model call, and replays cleanly against
  the current code. Every row's corpus `leakage_check` is `passed: true`.
- **Heuristic paraphrase warnings:** `validate_corpus.py` flags three rows for human review by
  word overlap. By the validator's own definition these are heuristic signals, not confirmed
  leakage. No human review of them has been recorded yet.

  | Row | Overlap flagged | `inclusion_status` | Eligible | Affects the formal figures? |
  |---|---|---|---|---|
  | ENV-DP16-03 | 54% with `ground_truth_evidence.quote` | include_as_borderline | no | no (not scored) |
  | JOSS-DP23-05 | 83% with `normative_basis` | include_as_borderline | no | no (not scored) |
  | RP-DP23-03 | 50% with `normative_basis` | include | yes | yes: scored in DP-23. Label `required`, predicted `sufficient_without` (incorrect) |

## Historical reconciliation: exclude-only figures (superseded, not current results)

The original `aggregate_report.json` in the source run was produced under the pre-ADR-007
exclude-only policy, which counted borderline rows marked ineligible. It is kept byte-identical
as historical evidence (ADR-006). The figures below are reproduced only so that document can be
reconciled with this one. They are **not** current results.

| Block | Exclude-only (superseded) | Eligible-only (authoritative) | Rows that account for the difference |
|---|---|---|---|
| DP-22 prefilter | n=6, 4/4 valid, coverage 0.667 | n=5, 4/4 valid, coverage 0.80 | ZEUS-DP22-01 |
| DP-22 System-1 | 1/2 | 0/1 | ZEUS-DP22-02 |
| DP-16 overall | 5/7 | 3/5 | ENV-DP16-03, JOSS-DP16-01 |
| DP-16 `positive_match` | 4/5 | 3/4 | ENV-DP16-03 |
| DP-16 `absence_based` | 1/2 | 0/1 | JOSS-DP16-01 |
| DP-23 | 5/12 | 3/10 | KC-DP23-01, JOSS-DP23-05 |

## What this evidence supports, and its limits

**Supported by the evidence:**
- A complete, leakage-preflighted prediction set exists for all 36 corpus rows. Its formal
  aggregate reproduces byte-for-byte offline from preserved predictions.
- Laya 0.3.20 produced a contract-valid output for all 29 rows it received.
- The prefilter's 4 handled, eligible rows were all correct. Of its 6 partition rows, it
  deferred 2.
- The eligible-only measurements in the results table above.

**Limited by sample size:**
- Every scored block has 10 or fewer eligible rows.
- DP-22 System-1 and DP-16 `absence_based` each have exactly one eligible row, so their
  figures are single observations.
- DP-23 has one eligible `sufficient_without` row, so its class balance allows almost no
  statement about that class.

**Not demonstrated:**
- Generalization beyond this corpus.
- Production readiness.
- Whether repeated inference gives the same predictions (inference was not rerun).
- Per-decision latency.
- Calibrated confidence.
- DP-11 accuracy.
- Any comparison with another system.

**Still open:**
- Human review of the three heuristic leakage warnings.
- A decision on the two prefilter-partition rows that no mechanism answers.

## Observations relevant to Phase 4.8

These are recorded as inputs only. None is an adoption or rejection decision.

- On the rows it handles, the DP-22 prefilter answered without any model tokens, and all of them
  were correct in this run. Two rows in its partition get no decision from any mechanism under
  the current routing.
- On DP-23, Laya's predictions (8 `sufficient_without`, 2 `required`) have a different
  distribution from the eligible labels (9 `required`, 1 `sufficient_without`).
- Laya's recorded cost profile is 95–214 input tokens and 0 output tokens per decision, across
  all 29 rows it answered. No per-decision latency was measured.
- The DeepSeek and Claude aggregate reports under `laya/results/` were produced under the
  superseded exclude-only policy. Under ADR-006, the Claude run is integration/smoke-test
  evidence only. Any cross-system comparison would first need those runs re-aggregated under
  ADR-007.

## Reproduction

These commands reproduce the historical record at commit `65e99aa` (or any later revision before
`6299603`, which still contains the original corpus). From `6299603` onward, the corpus hash
differs (ADR-008), and `10_rescore_offline.py` aborts at its corpus-hash check.

These commands need no model, network or GPU:

```sh
bash laya/harness/tests/run_all.sh        # deterministic harness self-tests
python3 laya/validate_corpus.py           # corpus contract validation
sha256sum laya/corpus/phase-4.1-decision-corpus.jsonl laya/results/phase4.5-laya-real-20260926T092215Z/*
python3 laya/harness/lib/10_rescore_offline.py laya/results/phase4.5-laya-real-20260926T092215Z
sha256sum laya/results/phase4.5-laya-real-20260926T092215Z--rescore-eligible-only-v1/aggregate_report.json
```

The last command should print the formal aggregate hash given under Evidence. Re-running the
rescore rewrites the derived `manifest.json`, which updates `generated_at` and records the
then-current `HEAD`.
