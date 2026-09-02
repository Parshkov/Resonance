# R11 independent-review hardening

This note records the two additional acceptance blockers found by the independent Fable exact-head review after the first R11 recovery round.

## Thought ID uniqueness / re-share policy

`thought_id` is a durable uniqueness key. Repository backends must translate uniqueness violations into `PersistenceConflictError`; raw SQLite/PostgreSQL driver exceptions are not part of the service contract and must not escape.

For v0.1 a `thought_id` remains reserved by its original session even after revoke/delete. A new session — including a deliberate re-share after deletion — must use a newly generated Thought DNA `thought_id`. This keeps tombstones immutable and avoids silently rebinding historical identity/provenance. The conflict response does not disclose which other owner/session holds the reservation.

## Projection validation / degraded restart

Product writes validate the R7-facing presentation boundary before commit:

- location is either empty while location sharing is disabled, or an exact allowlisted city-level object with `kind`, `region`, `city`, `lat`, `lon`, `precision`;
- unknown location fields are rejected;
- coordinates must be finite, in range, and rounded to 0.1 degree;
- presentation uses only non-empty `domain`, `topic`, `cluster_id` fields.

A pre-existing malformed discoverable row is treated as `PersistenceStateError` naming the affected session. Startup remains alive in a degraded/fail-closed state with no serving generation; discovery is unavailable, but ordinary authorized mutation/revocation/repair paths remain usable. Once the bad row is repaired (or made non-discoverable) a rebuild restores readiness.

The focused regressions live in `tests/test_persistence_fable_blockers.py`.
