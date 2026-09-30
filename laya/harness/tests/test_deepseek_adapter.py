#!/usr/bin/env python3
"""Self-tests for lib/deepseek_adapter.py. Completely model/API-free: a fake transport
callable stands in for the real HTTP client, and no network library is imported anywhere."""
from __future__ import annotations

import json

from _load_lib import load_lib_module
from adapter_base import build_canonical_result  # via _load_lib's sys.path insert of lib/

deepseek_adapter = load_lib_module("deepseek_adapter.py", "deepseek_adapter")

ALLOWED = ["required", "sufficient_without"]


def _fake_response(decision_content: str, prompt_tokens=100, completion_tokens=10, cache_hit=0, model="deepseek-flash"):
    return {
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": decision_content}}],
        "usage": {
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens, "prompt_cache_hit_tokens": cache_hit,
        },
    }


class _RecordingTransport:
    def __init__(self, response=None, exception=None):
        self.response = response
        self.exception = exception
        self.calls = []

    def __call__(self, request_body):
        self.calls.append(request_body)
        if self.exception:
            raise self.exception
        return self.response


def main() -> int:
    checks = []

    # --- request shape ---
    transport = _RecordingTransport(response=_fake_response('{"decision": "required"}'))
    adapter = deepseek_adapter.DeepSeekAdapter(transport)
    envelope = adapter.predict("human_acceptance_required", {"change_description": "x"}, ALLOWED)
    req = transport.calls[0]
    checks.append(("request contains the correct model", req["model"] == deepseek_adapter.DEFAULT_MODEL))
    checks.append(("request contains json_object response_format", req["response_format"] == {"type": "json_object"}))
    checks.append(("request contains explicit thinking configuration", req["thinking"] == {"type": "disabled"}))
    checks.append(("request contains explicit reasoning_effort configuration", req["reasoning_effort"] == "none"))
    checks.append(("request never silently omits configuration (both keys present)", "thinking" in req and "reasoning_effort" in req))
    user_msg = next(m for m in req["messages"] if m["role"] == "user")
    checks.append(("request contains the rendered prompt in the user message", "change_description" in user_msg["content"] and "\"x\"" in user_msg["content"]))
    system_msg = next(m for m in req["messages"] if m["role"] == "system")
    checks.append(("allowed values are represented in the system message", all(v in system_msg["content"] for v in ALLOWED)))
    checks.append(("system message preserves the contract's own decision_question verbatim",
                   json.loads((deepseek_adapter.PROMPTS_DIR / "human_acceptance_required.json").read_text())["decision_question"] in system_msg["content"]))

    # --- valid JSON decision succeeds ---
    checks.append(("a clean {\"decision\": \"required\"} succeeds", envelope.valid_prediction is True and envelope.predicted_value == "required"))
    checks.append(("error is None on success", envelope.error is None))

    # --- output validation: each malformed/invalid case, exact category ---
    def _predict_with_content(content):
        t = _RecordingTransport(response=_fake_response(content))
        return deepseek_adapter.DeepSeekAdapter(t).predict("human_acceptance_required", "x", ALLOWED)

    missing = _predict_with_content('{"other": "required"}')
    checks.append(("missing decision field fails", missing.valid_prediction is False and missing.error == "malformed_output: missing_decision"))

    invalid_json = _predict_with_content('not json at all {')
    checks.append(("invalid JSON fails with invalid_json category", invalid_json.valid_prediction is False and invalid_json.error == "malformed_output: invalid_json"))

    non_object = _predict_with_content('["required"]')
    checks.append(("a JSON array (non-object) fails with non_object category", non_object.valid_prediction is False and non_object.error == "malformed_output: non_object"))

    extra_keys = _predict_with_content('{"decision": "required", "confidence": 0.9}')
    checks.append(("extra keys fail with extra_keys category", extra_keys.valid_prediction is False and extra_keys.error == "malformed_output: extra_keys"))

    not_allowed = _predict_with_content('{"decision": "maybe"}')
    checks.append(("an off-contract decision value fails, never coerced", not_allowed.valid_prediction is False and not_allowed.error.startswith("invalid_output: decision_not_allowed")))
    checks.append(("an off-contract decision value has predicted_value=None", not_allowed.predicted_value is None))

    prose_wrapped = _predict_with_content('Here is the answer:\n{"decision":"required"}\n')
    checks.append(("prose surrounding valid JSON is malformed, never extracted/repaired", prose_wrapped.valid_prediction is False and prose_wrapped.error == "malformed_output: invalid_json"))

    non_string = _predict_with_content('{"decision": 1}')
    checks.append(("a non-string decision value fails with a precise category", non_string.valid_prediction is False and non_string.error == "malformed_output: decision_not_string"))

    # --- usage / token mapping ---
    usage_env = _predict_with_content('{"decision": "required"}')
    # _predict_with_content uses default prompt_tokens=100, completion_tokens=10, cache_hit=0
    checks.append(("prompt_tokens maps to input_tokens", usage_env.input_tokens == 100))
    checks.append(("completion_tokens maps to output_tokens", usage_env.output_tokens == 10))
    checks.append(("prompt_cache_hit_tokens maps to cache_read_tokens", usage_env.cache_read_tokens == 0))
    checks.append(("cache_write_tokens is always None (DeepSeek reports no such field)", usage_env.cache_write_tokens is None))

    # --- missing usage handled safely (not crashed, fields left None) ---
    no_usage_response = {"model": "deepseek-flash", "choices": [{"message": {"content": '{"decision": "required"}'}}]}
    no_usage_env = deepseek_adapter.DeepSeekAdapter(_RecordingTransport(response=no_usage_response)).predict("human_acceptance_required", "x", ALLOWED)
    checks.append(("missing usage dict is handled safely, not a crash", no_usage_env.valid_prediction is True))
    checks.append(("missing usage leaves token fields None, not zero", no_usage_env.input_tokens is None and no_usage_env.output_tokens is None and no_usage_env.cache_read_tokens is None))

    # --- latency ---
    checks.append(("latency_ms is recorded as a real measured float", isinstance(envelope.latency_ms, float) and envelope.latency_ms >= 0))

    # --- model identifier is deterministic ---
    checks.append(("model_identifier matches the documented example prefix",
                   deepseek_adapter.build_model_identifier("deepseek-flash", {"type": "disabled"}, "none").startswith("deepseek:deepseek-flash:thinking-disabled")))
    checks.append(("model_identifier distinguishes different reasoning_effort configurations",
                   deepseek_adapter.build_model_identifier("deepseek-flash", {"type": "enabled"}, "low")
                   != deepseek_adapter.build_model_identifier("deepseek-flash", {"type": "enabled"}, "high")))
    checks.append(("model_identifier construction is deterministic (same inputs -> same output)",
                   deepseek_adapter.build_model_identifier("deepseek-flash", {"type": "disabled"}, "none")
                   == deepseek_adapter.build_model_identifier("deepseek-flash", {"type": "disabled"}, "none")))

    # --- confidence / probability_distribution never fabricated ---
    checks.append(("confidence remains None even on a valid, successful prediction", envelope.confidence is None))
    checks.append(("probability_distribution remains None even on a valid, successful prediction", envelope.probability_distribution is None))

    # --- API/transport error becomes a PredictionEnvelope, no crash, no retry ---
    error_transport = _RecordingTransport(exception=TimeoutError("connection timed out"))
    error_adapter = deepseek_adapter.DeepSeekAdapter(error_transport)
    error_env = error_adapter.predict("human_acceptance_required", "x", ALLOWED)
    checks.append(("a transport exception becomes a PredictionEnvelope, never raises", error_env.valid_prediction is False and error_env.error.startswith("api_error")))
    checks.append(("no retry occurs after a transport failure", len(error_transport.calls) == 1))

    # --- adapter never receives corpus metadata ---
    import inspect
    sig_params = set(inspect.signature(deepseek_adapter.DeepSeekAdapter.predict).parameters)
    checks.append(("predict() signature has no candidate_id/corpus-row parameter", sig_params == {"self", "decision_type", "rendered_prompt", "allowed_output_values"}))

    # --- canonical result can be built from the envelope ---
    canonical = build_canonical_result("SYN-01", "human_acceptance_required", "run-1", "0" * 64, envelope)
    required_fields = {
        "candidate_id", "decision_type", "run_id", "model_identifier", "predicted_value",
        "valid_prediction", "latency_ms", "error", "timestamp", "corpus_content_hash",
    }
    checks.append(("a canonical result can be built from the envelope with every required field", required_fields <= set(canonical)))
    checks.append(("the canonical result carries the deepseek model_identifier through", canonical["model_identifier"] == envelope.model_identifier))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  deepseek_adapter checks failed: {failed}")
        return 1
    print(f"PASS  deepseek_adapter: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
