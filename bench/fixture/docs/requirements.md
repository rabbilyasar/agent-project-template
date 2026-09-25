# Requirements

## Functional Requirements

- REQ-010 — Rate limit `/widgets` per client. Status: Accepted, not yet implemented.
  A client must not receive more than N `/widgets` responses per rolling minute; requests over the
  limit must receive HTTP 429. N is configurable.

## Requirement Status

- **Accepted** — agreed and part of project scope, not yet implemented.
- **Implemented** — implementation is complete.
