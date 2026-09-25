import { test } from "node:test";
import assert from "node:assert/strict";
import { TtlCache } from "../src/cache.js";

// Hidden regression test for bench/tasks/investigation-debugging.md. Not
// shown to the agent during the trial; copied in only by
// harness/lib/06_validate.sh after the trial ends.
test("get() returns undefined once a key has expired", () => {
  let now = 0;
  const cache = new TtlCache<string>(() => now);
  cache.set("k", "v", 100);
  now = 200;
  assert.equal(cache.get("k"), undefined);
});
