import { test } from "node:test";
import assert from "node:assert/strict";
import { defaultConfig } from "../src/config.js";

test("defaultConfig has a positive maxRetries", () => {
  assert.ok(defaultConfig.maxRetries > 0);
});
