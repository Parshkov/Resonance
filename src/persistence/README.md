# R11 Persistence Recovery

Durable multi-user product storage for Resonance, recovered from the useful
foundation in superseded PR #95 with full derivation provenance. The accepted
structural retrieval/alignment/verifier/scoring stack is unchanged.

`demo/corpus/*.jsonl` remains a deterministic fixture/replay seed only. It is
not the live product database.

## Backends

- **SQLite file** — deterministic local/judge/reset backend, stdlib only.
- **PostgreSQL** — hosted-pilot backend behind the same repository contract.
  Set `RESONANCE_DATABASE_URL=postgresql://...` and install `psycopg` or
  `psycopg2`.

Canonical SQL migrations live in `ops/migrations/`.

## Recovery invariants

### DB is authoritative; discovery fails closed

A singleton `persistence_state.corpus_generation` advances in the **same DB
transaction** as every product-visible user/session mutation. `LiveCorpusService`
holds a `serving_generation` for the currently published engine + consent
registry. Discovery is allowed only when:

1. serving generation equals durable DB generation; and
2. accepted engine store/index snapshots are internally bound.

The service marks itself stale before a visibility-affecting write. If the DB
commit succeeds but rebuilding the in-memory index fails, discovery raises
`PersistenceStaleIndexError`; the old generation is never served. A restart or
successful rebuild reconstructs deterministic state from the DB.

### Immutable ownership

`session_id -> user_id` is immutable in normal product writes. The repository
checks ownership inside its write transaction (`BEGIN IMMEDIATE` on SQLite,
`SELECT ... FOR UPDATE` on PostgreSQL). Import/restore is a separately named
privileged administrative path.

This persistence API is an **internal data-layer seam**, not an authorization
API. R12/R12B's authenticated subject-scoped service is the only intended
transport-facing mutation boundary for UI, WebMCP, and remote MCP.

### Optimistic concurrency

Each session has a monotonic integer `version`. Updating an existing session
requires the current `expected_version`; stale writes raise
`PersistenceConflictError` rather than silently overwriting a newer consent or
revocation decision.

Convenience mutation methods (`update_consent`, `update_presentation`, revoke,
delete) use the version they just read when the caller omits it, while external
subject-scoped services should pass the version they exposed to the caller.

### Durable retry / idempotency

State-changing session methods accept an optional `request_id`. The repository
stores `(request_id, operation, request_hash, response)` transactionally with
the mutation, audit event, and generation bump.

- same request ID + same payload => original committed result;
- same request ID + different payload => conflict;
- timeout after DB commit but before rebuild => retry returns original DB result
  and heals the stale serving generation without applying the mutation twice.

This is required because browser/agent clients may automatically retry writes.

## Data retained

At minimum:

- pseudonymous users/profiles;
- owned sessions;
- validated Thought DNA JSON + schema/version/hash/provenance;
- independent per-session consent flags;
- optional display profile and consented/synthetic coarse location;
- timestamps, revocation/deletion state, optimistic version;
- minimized audit events;
- durable idempotency records;
- schema room for later intros/channels/messages.

Raw private conversation text is not required by this persistence layer.

## Deterministic engine boundary

Only live, discoverable, validated Thought DNA is indexed. Rebuild order is
sorted by `thought_id`. User/display/location metadata joins after matching and
never enters retrieval, alignment, verification, or scoring. A discoverable DB
row with invalid/unsupported Thought DNA makes rebuild fail closed instead of
being silently skipped.

## Operations

```bash
python3 -m src.persistence --db var/resonance-pilot.sqlite migrate
python3 -m src.persistence --db var/resonance-pilot.sqlite seed-r7
python3 -m src.persistence --db var/resonance-pilot.sqlite seed-pilot --count 100
python3 -m src.persistence --db var/resonance-pilot.sqlite health
python3 -m src.persistence --db var/resonance-pilot.sqlite export --out var/backup.json
python3 -m src.persistence --db var/resonance-pilot.sqlite import-backup var/backup.json
python3 -m src.persistence --db var/resonance-pilot.sqlite reset
```

`health` reports both durable `db_generation` and `serving_generation` plus
`index_current`. A stale generation makes readiness fail.

## Backup / restore

`export` writes structured pilot records, audit evidence, session versions,
idempotency results, and generation metadata. Restore is an explicit
repository-admin operation; it replaces product records transactionally, bumps
the durable generation, and requires a deterministic rebuild before readiness.

Hosted PostgreSQL should additionally use the provider's encrypted/access-
controlled backup mechanism; the JSON export is the portable application-level
path, not a substitute for managed database backup.

## Validation boundary

The recovery branch contains deterministic tests for:

- R7 seed parity and metadata ranking invariance;
- >=100 users/sessions and restart persistence;
- revoke/delete/consent failure immediately after DB commit;
- stale-index fail-closed behavior and restart recovery;
- immutable ownership;
- stale-version rejection;
- duplicate request IDs and retry-after-timeout semantics;
- generation-aware readiness;
- backup/restore;
- concurrent create/discover smoke;
- absence of matcher implementation imports in persistence.

Full repository and live PostgreSQL execution must be reported from a
clone-capable runner/CI; they must never be inferred from source inspection.
