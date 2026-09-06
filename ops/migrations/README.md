# Persistence migrations

These SQL files are the canonical versioned R11 database migrations used by
the PostgreSQL repository.

- `0001_init.sql` preserves the schema shape contributed by the superseded Grok
  R11 foundation PR #95 so an already-created development DB can upgrade.
- `0002_recovery_generation.sql` is the recovery migration adding optimistic
  session versions, durable DB/index generation state, and idempotency records.

Migrations are applied in lexical order and recorded in `schema_migrations`.
Never edit an already-applied migration to change live schema semantics; add a
new numbered migration instead.

For hosted PostgreSQL, migrations should run with the same application release
before readiness is enabled. `LiveCorpusService.health()` additionally requires
the serving in-memory index generation to equal the durable DB generation.
