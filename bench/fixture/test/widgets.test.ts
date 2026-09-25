import { test } from "node:test";
import assert from "node:assert/strict";
import { listWidgets } from "../src/widgets.js";

test("listWidgets returns the known widgets for a client", () => {
  const widgets = listWidgets("client-a");
  assert.equal(widgets.length, 2);
});
