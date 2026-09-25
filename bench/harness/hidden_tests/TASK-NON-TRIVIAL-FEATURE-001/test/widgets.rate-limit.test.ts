import { test } from "node:test";
import assert from "node:assert/strict";
import { listWidgets } from "../src/widgets.js";

// Hidden acceptance test for bench/tasks/non-trivial-feature.md (REQ-010).
// Not shown to the agent during the trial. Assumes the implementation
// surfaces the limit decision by throwing a RateLimitError (or equivalent)
// that the harness's own HTTP-layer check (out of scope for this unit-level
// stub) maps to a 429 -- adjust the assertion here once the agent's actual
// interface for signaling "limited" is known, since REQ-010 does not
// prescribe one.
test("listWidgets stops succeeding once a client exceeds the configured limit", () => {
  const clientId = "rate-limit-test-client";
  let sawLimit = false;
  for (let i = 0; i < 1000; i++) {
    try {
      listWidgets(clientId);
    } catch {
      sawLimit = true;
      break;
    }
  }
  assert.ok(sawLimit, "expected some call to be rejected once the per-minute limit is exceeded");
});
