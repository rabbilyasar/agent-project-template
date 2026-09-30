#!/usr/bin/env python3
"""Self-tests for lib/claude_adapter.py. Completely model/API-free: a fake transport
callable stands in for the real HTTP client, and no network library is imported anywhere."""
from __future__ import annotations

import json

from _load_lib import load_lib_module
from adapter_base import build_canonical_result

claude_adapter = load_lib_module("claude_adapter.py", "claude_adapter")

ALLOWED = ["required", "sufficient_without"]


def _fake_response(decision_content, input_tokens=100, output_tokens=10, cache_read=0, cache_write=0, model="claude-haiku-4-5-20251001"):
    return {
        "id": "msg_fake", "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": decision_content}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cache_read_input_tokens": cache_read, "cache_creation_input_tokens": cache_write,
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

    transport = _RecordingTransport(response=_fake_response('{"decision": "required"}'))
    adapter = claude_adapter.ClaudeAdapter(transport)
    envelope = adapter.predict("human_acceptance_required", {"change_description": "x"}, ALLOWED)
    req = transport.calls[0]

    checks.append(("request contains the correct model", req["model"] == claude_adapter.DEFAULT_MODEL))
    checks.append(("request contains a max_tokens cap", isinstance(req["max_tokens"], int) and req["max_tokens"] > 0))
    checks.append(("request contains the rendered prompt in the user message", "change_description" in req["messages"][0]["content"]))
    checks.append(("allowed values are represented in the system message", all(v in req["system"] for v in ALLOWED)))
    checks.append(("system message preserves the contract's own decision_question verbatim",
                   json.loads((claude_adapter.PROMPTS_DIR / "human_acceptance_required.json").read_text())["decision_question"] in req["system"]))
    checks.append(("no candidate_id/corpus metadata anywhere in the request body", "candidate_id" not in json.dumps(req)))

    checks.append(("a clean {\"decision\": \"required\"} succeeds", envelope.valid_prediction is True and envelope.predicted_value == "required"))
    checks.append(("error is None on success", envelope.error is None))

    def _predict_with_content(content):
        t = _RecordingTransport(response=_fake_response(content))
        return claude_adapter.ClaudeAdapter(t).predict("human_acceptance_required", "x", ALLOWED)

    missing = _predict_with_content('{"other": "required"}')
    checks.append(("missing decision field fails (shared validator, reused not duplicated)", missing.valid_prediction is False and missing.error == "malformed_output: missing_decision"))

    invalid_json = _predict_with_content("not json")
    checks.append(("invalid JSON fails", invalid_json.valid_prediction is False and invalid_json.error == "malformed_output: invalid_json"))

    not_allowed = _predict_with_content('{"decision": "maybe"}')
    checks.append(("an off-contract decision value fails, never coerced", not_allowed.valid_prediction is False and not_allowed.predicted_value is None))

    checks.append(("parse_decision_content is literally imported from deepseek_adapter, not duplicated",
                   claude_adapter.parse_decision_content.__module__ == "deepseek_adapter"))

    missing_content = claude_adapter.ClaudeAdapter(_RecordingTransport(response={"id": "msg_fake", "usage": {}})).predict("human_acceptance_required", "x", ALLOWED)
    checks.append(("a response missing content blocks is malformed_output, not a crash", missing_content.valid_prediction is False and missing_content.error == "malformed_output: missing_content"))

    usage_env = _predict_with_content('{"decision": "required"}')
    checks.append(("input_tokens mapped from usage.input_tokens", usage_env.input_tokens == 100))
    checks.append(("output_tokens mapped from usage.output_tokens", usage_env.output_tokens == 10))
    checks.append(("cache_read_tokens mapped from usage.cache_read_input_tokens", usage_env.cache_read_tokens == 0))
    checks.append(("cache_write_tokens mapped from usage.cache_creation_input_tokens (Claude reports both, unlike DeepSeek)", usage_env.cache_write_tokens == 0))

    no_usage_response = {"content": [{"type": "text", "text": '{"decision": "required"}'}]}
    no_usage_env = claude_adapter.ClaudeAdapter(_RecordingTransport(response=no_usage_response)).predict("human_acceptance_required", "x", ALLOWED)
    checks.append(("missing usage handled safely, not a crash", no_usage_env.valid_prediction is True))
    checks.append(("missing usage leaves token fields None, not zero", no_usage_env.input_tokens is None and no_usage_env.output_tokens is None and no_usage_env.cache_read_tokens is None and no_usage_env.cache_write_tokens is None))

    checks.append(("latency_ms is recorded as a real measured float", isinstance(envelope.latency_ms, float) and envelope.latency_ms >= 0))

    checks.append(("model_identifier is deterministic and includes the actual model",
                   claude_adapter.build_model_identifier("claude-haiku-4-5-20251001") == "claude:claude-haiku-4-5-20251001:direct-api"))
    checks.append(("model_identifier distinguishes different models",
                   claude_adapter.build_model_identifier("claude-haiku-4-5-20251001") != claude_adapter.build_model_identifier("claude-sonnet-5")))

    checks.append(("confidence remains None even on a valid, successful prediction", envelope.confidence is None))
    checks.append(("probability_distribution remains None even on a valid, successful prediction", envelope.probability_distribution is None))

    # Regression: the historical phase4-claude-claude-haiku-4-5-20251001-real-20260926T112904Z
    # run showed Claude Haiku 4.5 wrapping its entire answer in a markdown code fence despite
    # JSON_TRANSPORT_INSTRUCTION_TEMPLATE explicitly forbidding it, producing 24/36
    # malformed_output: invalid_json rows. The adapter now unwraps a *whole-response* fence
    # before parsing -- but must not become a general JSON-in-prose extractor.
    fenced = _predict_with_content('```json\n{"decision": "required"}\n```')
    checks.append(("a markdown-fenced JSON response (the historical Claude Haiku failure mode) now parses successfully",
                   fenced.valid_prediction is True and fenced.predicted_value == "required"))

    fenced_no_lang_tag = _predict_with_content('```\n{"decision": "required"}\n```')
    checks.append(("a fence with no language tag also unwraps",
                   fenced_no_lang_tag.valid_prediction is True and fenced_no_lang_tag.predicted_value == "required"))

    prose_wrapped = _predict_with_content('Sure, here is the answer:\n```json\n{"decision": "required"}\n```')
    checks.append(("JSON embedded in surrounding prose is still rejected, never broadly extracted",
                   prose_wrapped.valid_prediction is False and prose_wrapped.error == "malformed_output: invalid_json"))

    unclosed_fence = _predict_with_content('```json\n{"decision": "required"}')
    checks.append(("an unclosed/malformed fence is still rejected, not partially repaired",
                   unclosed_fence.valid_prediction is False and unclosed_fence.error == "malformed_output: invalid_json"))

    error_transport = _RecordingTransport(exception=TimeoutError("connection timed out"))
    error_adapter = claude_adapter.ClaudeAdapter(error_transport)
    error_env = error_adapter.predict("human_acceptance_required", "x", ALLOWED)
    checks.append(("a transport exception becomes a PredictionEnvelope, never raises", error_env.valid_prediction is False and error_env.error.startswith("api_error")))
    checks.append(("no retry occurs after a transport failure", len(error_transport.calls) == 1))

    import inspect
    sig_params = set(inspect.signature(claude_adapter.ClaudeAdapter.predict).parameters)
    checks.append(("predict() signature has no candidate_id/corpus-row parameter", sig_params == {"self", "decision_type", "rendered_prompt", "allowed_output_values"}))

    canonical = build_canonical_result("SYN-01", "human_acceptance_required", "run-1", "0" * 64, envelope)
    required_fields = {
        "candidate_id", "decision_type", "run_id", "model_identifier", "predicted_value",
        "valid_prediction", "latency_ms", "error", "timestamp", "corpus_content_hash",
    }
    checks.append(("a canonical result can be built from the envelope with every required field", required_fields <= set(canonical)))
    checks.append(("the canonical result carries the claude model_identifier through", canonical["model_identifier"] == envelope.model_identifier))

    failed = [name for name, ok in checks if not ok]
    if failed:
        print(f"FAIL  claude_adapter checks failed: {failed}")
        return 1
    print(f"PASS  claude_adapter: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
