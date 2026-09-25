# Architecture Decisions

### ADR-001 — In-process TTL cache instead of an external cache store

**Status:** Accepted

**Date:** 2025-01-01

**Context**

`/widgets` responses are cheap to compute but called frequently per client.

**Decision**

Use a small in-process `TtlCache` (`src/cache.ts`) rather than an external cache service.

**Rationale**

This fixture is intentionally small; an external cache would add operational surface with no
benefit at this scale.

**Consequences**

Cache state is per-process and lost on restart. Acceptable for this project's scale.
