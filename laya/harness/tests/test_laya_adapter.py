#!/usr/bin/env python3
"""Self-tests for lib/laya_adapter.py. Uses a stub agent object (no torch/laya import,
no GPU) except for one regression guard that reuses the existing, already-proven
01_load_corpus loader (still zero Laya/GPU dependency)."""
from __future__ import annotations

import json

from _load_lib import load_lib_module

laya_adapter = load_lib_module("laya_adapter.py", "laya_adapter")
load_corpus_mod = load_lib_module("01_load_corpus.py", "load_corpus")

ALL_DECISION_TYPES = [
    "trivial_vs_staged", "agent_verification_applicable",
    "documented_limitation_vs_defect", "human_acceptance_required",
]


class _FakeAgent:
    def __init__(self, single_response=None, single_exception=None, batch_responses=None, batch_exception=None):
        self.single_response = single_response
        self.single_exception = single_exception
        self.batch_responses = batch_responses
        self.batch_exception = batch_exception
        self.predict_calls = []
        self.predict_batch_calls = []

    def predict(self, state, questions):
        self.predict_calls.append((state, questions))
        if self.single_exception:
            raise self.single_exception
        return self.single_response

    def predict_batch(self, states, questions, batch_size=None, sort_by_length=False):
        self.predict_batch_calls.append((list(states), questions, batch_size, sort_by_length))
        if self.batch_exception:
            raise self.batch_exception
        return self.batch_responses


def _laya_response(choice, probabilities, confidence=0.1, answer_confidence=None, input_tokens=50, output_tokens=0):
    if answer_confidence is None:
        answer_confidence = max(probabilities.values())
    return {
        "model": "laya-rl-agent",
        "answers": {
            "decision": {
                "type": "choice", "choice": choice, "probabilities": probabilities,
                "confidence": confidence, "answer_confidence": answer_confidence,
                "action": {"act_probability": 1.0},
            }
        },
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


def main() -> int:
    checks = []

    # --- #1 adapter contract shape ---
    stub_agent = _FakeAgent(single_response=_laya_response("trivial", {"trivial": 0.9, "staged": 0.1}))
    adapter = laya_adapter.LayaAdapter(stub_agent, model_identifier="laya:0.3.20:convaiinnovations/laya-typed-decisions")
    checks.append(("LayaAdapter exposes model_identifier", adapter.model_identifier == "laya:0.3.20:convaiinnovations/laya-typed-decisions"))
    checks.append(("LayaAdapter.predict signature has no corpus/candidate_id params",
                   set(laya_adapter.LayaAdapter.predict.__code__.co_varnames[:4]) == {"self", "decision_type", "rendered_prompt", "allowed_output_values"}))

    # --- #2 four decision -> Laya question mappings ---
    for decision_type in ALL_DECISION_TYPES:
        contract = laya_adapter._load_contract(decision_type)
        questions = laya_adapter.build_questions(contract)
        checks.append((f"{decision_type}: exactly one 'decision' question", set(questions) == {"decision"}))
        q = questions["decision"]
        checks.append((f"{decision_type}: type is choice", q["type"] == "choice"))
        checks.append((f"{decision_type}: instructions is decision_question verbatim", q["instructions"] == contract["decision_question"]))
        checks.append((f"{decision_type}: criteria keys exactly match allowed_output_values",
                       set(q["criteria"]) == set(contract["allowed_output_values"])))

    # --- #5 DP-23 normative-only: no empirical content anywhere in the Laya-facing question ---
    dp23_contract = laya_adapter._load_contract("human_acceptance_required")
    dp23_questions = laya_adapter.build_questions(dp23_contract)
    checks.append(("DP-23 Laya question never mentions empirical fields", "empirical" not in json.dumps(dp23_questions).lower()))
    dp23_rows = [r for r in load_corpus_mod.load_corpus()[0] if r.decision_type == "human_acceptance_required"]
    checks.append(("DP-23 rows exist in the real corpus", len(dp23_rows) == 12))
    checks.append(("real DP-23 model_facing_input never contains empirical content",
                   all("empirical" not in json.dumps(load_corpus_mod.model_facing_payload(r)).lower() for r in dp23_rows)))

    # --- #6 DP-22 routing ---
    checks.append(("system1_judgment DP-22 row is eligible", laya_adapter.is_eligible_for_laya("agent_verification_applicable", "system1_judgment") is True))
    checks.append(("deterministic_prefilter_validation DP-22 row is NOT eligible", laya_adapter.is_eligible_for_laya("agent_verification_applicable", "deterministic_prefilter_validation") is False))
    checks.append(("excluded (partition=None) DP-22 row is NOT eligible", laya_adapter.is_eligible_for_laya("agent_verification_applicable", None) is False))
    checks.append(("non-DP-22 decision types are unconditionally eligible", laya_adapter.is_eligible_for_laya("trivial_vs_staged", None) is True))
    all_rows, _ = load_corpus_mod.load_corpus()
    dp22_rows = [r for r in all_rows if r.decision_type == "agent_verification_applicable"]
    eligible_ids = {r.candidate_id for r in dp22_rows if laya_adapter.is_eligible_for_laya(r.decision_type, r.raw.get("corpus_partition"))}
    checks.append(("real corpus: exactly the 2 system1_judgment DP-22 rows are eligible for Laya", eligible_ids == {"ZEUS-DP22-02", "ZEUS-DP22-03"}))

    # --- #3 allowed-output validation (never coerce) ---
    bad_agent = _FakeAgent(single_response=_laya_response("maybe", {"maybe": 1.0}))
    bad_adapter = laya_adapter.LayaAdapter(bad_agent, model_identifier="m")
    bad_env = bad_adapter.predict("trivial_vs_staged", {"task_description": "x"}, ["trivial", "staged"])
    checks.append(("off-contract choice is never coerced into a valid prediction", bad_env.valid_prediction is False and bad_env.predicted_value is None))
    checks.append(("off-contract choice reports an invalid_output error", bad_env.error is not None and bad_env.error.startswith("invalid_output")))
    checks.append(("off-contract choice nulls confidence/probability_distribution too", bad_env.confidence is None and bad_env.probability_distribution is None))

    # --- #4 malformed output ---
    malformed_agent = _FakeAgent(single_response={"model": "laya-rl-agent", "usage": {"input_tokens": 1, "output_tokens": 0}})  # no "answers" key
    malformed_env = laya_adapter.LayaAdapter(malformed_agent, "m").predict("trivial_vs_staged", "x", ["trivial", "staged"])
    checks.append(("missing answers key is a malformed_output error, not a crash", malformed_env.valid_prediction is False and malformed_env.error.startswith("malformed_output")))

    exc_agent = _FakeAgent(single_exception=RuntimeError("boom"))
    exc_env = laya_adapter.LayaAdapter(exc_agent, "m").predict("trivial_vs_staged", "x", ["trivial", "staged"])
    checks.append(("an inference exception never propagates out of predict()", exc_env.valid_prediction is False and exc_env.error.startswith("inference_exception")))

    # --- #7 answer_confidence extraction (never entropy-derived "confidence") ---
    good_agent = _FakeAgent(single_response=_laya_response("staged", {"trivial": 0.2, "staged": 0.8}, confidence=0.05, answer_confidence=0.8))
    good_env = laya_adapter.LayaAdapter(good_agent, "m").predict("trivial_vs_staged", "x", ["trivial", "staged"])
    checks.append(("canonical confidence uses answer_confidence, not Laya's entropy confidence", good_env.confidence == 0.8 and good_env.confidence != 0.05))

    # --- #8 probability distribution extraction ---
    checks.append(("probability_distribution matches raw probabilities exactly", good_env.probability_distribution == {"trivial": 0.2, "staged": 0.8}))

    # --- #9 missing probability handling ---
    no_prob_response = {
        "model": "laya-rl-agent",
        "answers": {"decision": {"type": "choice", "choice": "staged"}},
        "usage": {"input_tokens": 30, "output_tokens": 0},
    }
    no_prob_env = laya_adapter.LayaAdapter(_FakeAgent(single_response=no_prob_response), "m").predict("trivial_vs_staged", "x", ["trivial", "staged"])
    checks.append(("prediction can still be valid without a probability distribution", no_prob_env.valid_prediction is True and no_prob_env.predicted_value == "staged"))
    checks.append(("missing probabilities -> confidence is None, not fabricated", no_prob_env.confidence is None))
    checks.append(("missing probabilities -> probability_distribution is None", no_prob_env.probability_distribution is None))

    # --- #10 usage extraction ---
    checks.append(("input_tokens extracted from usage", good_env.input_tokens == 50))
    checks.append(("output_tokens=0 is preserved as a real zero, not None", good_env.output_tokens == 0 and good_env.output_tokens is not None))
    checks.append(("cache_read_tokens is always None (no cache concept in Laya)", good_env.cache_read_tokens is None))
    checks.append(("cache_write_tokens is always None (no cache concept in Laya)", good_env.cache_write_tokens is None))

    # --- #11 explicit CUDA configuration validation (pure function, no torch import) ---
    try:
        laya_adapter.require_device_available("cuda", False)
        checks.append(("cuda configured + unavailable raises, never silently falls back", False))
    except laya_adapter.LayaAdapterError:
        checks.append(("cuda configured + unavailable raises, never silently falls back", True))
    try:
        laya_adapter.require_device_available("cuda", True)
        checks.append(("cuda configured + available does not raise", True))
    except laya_adapter.LayaAdapterError:
        checks.append(("cuda configured + available does not raise", False))
    try:
        laya_adapter.require_device_available("cpu", False)
        checks.append(("a non-cuda device never triggers the cuda availability check", True))
    except laya_adapter.LayaAdapterError:
        checks.append(("a non-cuda device never triggers the cuda availability check", False))

    # --- #12 batch/result correspondence ---
    batch_agent = _FakeAgent(batch_responses=[
        _laya_response("trivial", {"trivial": 0.6, "staged": 0.4}),
        _laya_response("staged", {"trivial": 0.1, "staged": 0.9}),
        _laya_response("trivial", {"trivial": 0.7, "staged": 0.3}),
    ])
    batch_adapter = laya_adapter.LayaAdapter(batch_agent, "m")
    batch_envs = batch_adapter.predict_batch("trivial_vs_staged", ["state-A", "state-B", "state-C"], ["trivial", "staged"])
    checks.append(("predict_batch returns one envelope per input, in order", [e.predicted_value for e in batch_envs] == ["trivial", "staged", "trivial"]))
    checks.append(("predict_batch passes states through unchanged and in order", batch_agent.predict_batch_calls[0][0] == ["state-A", "state-B", "state-C"]))
    checks.append(("predict_batch uses batch_size=None, sort_by_length=False (fixed, not configurable)",
                   batch_agent.predict_batch_calls[0][2] is None and batch_agent.predict_batch_calls[0][3] is False))
    checks.append(("predict_batch shares one questions dict across the whole batch", batch_agent.predict_batch_calls[0][1] == laya_adapter.build_questions(laya_adapter._load_contract("trivial_vs_staged"))))

    # --- #13 batch failure handling ---
    failing_batch_agent = _FakeAgent(batch_exception=RuntimeError("gpu oom"))
    failing_envs = laya_adapter.LayaAdapter(failing_batch_agent, "m").predict_batch("trivial_vs_staged", ["s1", "s2"], ["trivial", "staged"])
    checks.append(("a batch-level failure marks every item in that batch failed", len(failing_envs) == 2 and all(e.valid_prediction is False for e in failing_envs)))
    checks.append(("batch failure error is attributed to the batch, not guessed per-row", all(e.error.startswith("batch_failed") for e in failing_envs)))
    checks.append(("batch failure does not fabricate a per-row latency", all(e.latency_ms is None for e in failing_envs)))

    mismatched_agent = _FakeAgent(batch_responses=[_laya_response("trivial", {"trivial": 1.0, "staged": 0.0})])  # 1 result for 2 inputs
    mismatched_envs = laya_adapter.LayaAdapter(mismatched_agent, "m").predict_batch("trivial_vs_staged", ["s1", "s2"], ["trivial", "staged"])
    checks.append(("a result/input count mismatch is a malformed_output error for every item, not a silent misalignment",
                   len(mismatched_envs) == 2 and all(e.error.startswith("malformed_output") for e in mismatched_envs)))

    # --- #15 model identifier construction ---
    checks.append(("build_model_identifier produces the documented stable format",
                   laya_adapter.build_model_identifier("0.3.20", "convaiinnovations/laya-typed-decisions")
                   == "laya:0.3.20:convaiinnovations/laya-typed-decisions"))
    checks.append(("every envelope this adapter produces carries the given model_identifier",
                   good_env.model_identifier == "m" and no_prob_env.model_identifier == "m"))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  laya_adapter checks failed: {failed}")
        return 1
    print(f"PASS  laya_adapter: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
