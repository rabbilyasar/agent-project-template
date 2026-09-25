import { test } from "node:test";
import assert from "node:assert/strict";
import { TtlCache } from "../src/cache.js";

test("has() reports false once a key expires", () => {
  let now = 0;
  const cache = new TtlCache<string>(() => now);
  cache.set("k", "v", 100);
  now = 200;
  assert.equal(cache.has("k"), false);
});
