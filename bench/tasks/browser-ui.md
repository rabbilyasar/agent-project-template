---
id: TASK-BROWSER-UI-001
class: browser-ui
title: Disable submit button and show a loading state during fetch
---

## Scenario / Setup

Starting repository: `bench/fixture` at its pinned commit, with the arm's template stamped in.
`web/app.js` submits the form and fetches `/widgets` without disabling the button or indicating a
loading state.

## Prompt

> Fix the submit button on the widgets page so it's disabled while the request is in flight, and
> show a loading state.

## Expected Behavior

The button is disabled for the duration of the fetch and re-enabled afterward; some visible
loading indication is shown while the request is pending. Per this project's own validation
procedure, the agent actually runs the pinned Playwright suite against the change rather than
only reasoning about it.

## Deterministic Validation

- A hidden Playwright spec, supplied by the harness only during validation
  (`bench/harness/hidden_tests/browser-ui/`), loads the page, submits the form, and asserts the
  button is disabled immediately after submit and enabled again once the response resolves.
- The harness's transcript inspection separately confirms the agent actually invoked the pinned
  Playwright binary (`npm run e2e` or equivalent) during the trial, not just edited files.

## Success Criteria

- Hidden Playwright spec passes.
- Tool-call log shows a real browser verification run.

## Allowed File Scope

- `web/app.js`
- `web/index.html` (only if a loading-state element needs to be added)
