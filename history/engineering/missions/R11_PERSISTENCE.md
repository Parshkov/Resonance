# R11-PERSISTENCE — Durable multi-user store and live corpus adapter

> **Superseded in part (2026-09-06).** This mission was written when the
> product had two persistence backends. Resonance now runs on **PostgreSQL
> only** — `src/persistence/sqlite_store.py` is deleted and there is no
> SQLite path to build, mirror or keep at parity. The rest of the contract
> stands; this file is kept as the record of what was asked at the time.

Issue: #83  
Recovery run: `R11-PERSISTENCE-RECOVERY-Q8V3`

## Objective

Replace repository-only/static fixture data as the live product source of truth
with a durable multi-user datastore while preserving all accepted structural
matching semantics.

`demo/corpus/*.jsonl` remains a deterministic seed/replay asset.

## Recovery provenance

This run starts from current accepted `main`, not from the superseded R11
branch. It intentionally reuses and ports useful architecture/code from the
Grok 4.6 canonical R11 submission, PR #95, with explicit attribution. PR #95
was closed as superseded after its author became unavailable and maintainer
review found acceptance-critical stale-index and ownership defects.

This is therefore a recovery/takeover, not a blind or independent rewrite.

## Owned surface

- `src/persistence/**`
- `ops/migrations/**`
- `tests/test_persistence.py`
- this mission/run documentation

Do not modify R2/R3/R4/R5/R6/R7/R8 matching algorithms, thresholds, gold data,
or accepted structural ranking semantics.

## Hard recovery invariants

1. **DB-authoritative visibility.** Durable state is authoritative. An old
   in-memory index must never continue serving after a newer DB visibility
   mutation commits.
2. **Generation barrier.** Every product-visible DB mutation advances a durable
   corpus generation atomically. Discovery serves only an engine/registry built
   for that exact generation.
3. **Fail closed.** Rebuild failure after share/revoke/delete/consent commit
   makes readiness/discovery fail until a successful deterministic rebuild.
4. **Immutable ownership.** Normal writes cannot reassign a `session_id` from
   one `user_id` to another. Restore/migration is an explicitly privileged path.
5. **Optimistic concurrency.** Session mutations are versioned; stale expected
   versions fail instead of overwriting newer consent/revocation state.
6. **Retry safety.** Optional durable `request_id` idempotency prevents agent or
   browser retries from applying the same state mutation twice, including after
   a timeout between DB commit and index rebuild.
7. **One matching implementation.** Persistence indexes only validated,
   discoverable Thought DNA into the accepted engine. Metadata/location never
   changes matching order, scores, verifier output, or evidence.
8. **Transport-neutral internal seam.** R11 repository/service methods are data
   layer APIs. R12/R12B authenticated subject-scoped services are the only
   intended transport-facing mutation boundary.

## Required operations

- versioned migrations (`ops/migrations/`);
- SQLite deterministic local/judge path;
- PostgreSQL hosted-pilot implementation behind the same repository contract;
- health/readiness including DB generation vs serving generation;
- accepted R7 fixture importer;
- clean judge/test reset;
- portable JSON export/import plus documented managed-DB backup expectation;
- deterministic restart-safe rebuild;
- synthetic >=100-user/session pilot seed;
- concurrent create/discover smoke.

## Acceptance evidence required

- >=100 users/sessions survive restart;
- revoke/delete/consent-off disappear immediately from DB public projection and
  cannot be returned by stale discovery if rebuild fails;
- same state remains absent after restart/rebuild;
- hidden users do not affect discovery or aggregates;
- display/location metadata permutation cannot affect structural order/scores;
- conflicting ownership transfer is rejected inside repository transaction;
- stale version update is rejected;
- duplicate request ID with same request is replayed once, while reuse for a
  different request fails;
- retry-after-commit/before-rebuild heals without a second mutation;
- R7 seed is create-only and does not overwrite live state on rerun;
- PostgreSQL contract is exercised where an isolated test DSN is available;
- existing engine/discovery regression suite remains green;
- `git diff --check` clean;
- exact-head independent review after SUBMIT.

## Environment truthfulness

A green source review is not execution evidence. If an agent runtime cannot
obtain a full checkout or PostgreSQL instance, it must report that limitation
and leave executable tests/commands for a clone-capable CI/reviewer rather than
inventing results.
