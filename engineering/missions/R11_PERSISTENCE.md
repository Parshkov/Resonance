# R11-PERSISTENCE — Durable multi-user store and live corpus adapter

Issue: #83

## Objective

Replace the repository-only demo corpus as the product source of truth with a
durable multi-user datastore while preserving accepted matching semantics.

`demo/corpus/*.jsonl` remains a deterministic fixture/replay asset.

## Ownership

`src/persistence/**`, `tests/test_persistence.py`, this mission file.
Do not change accepted R2/R3/R4/R5/R6/R7/R8 matching, gold, or thresholds.

## Start conditions

May begin in parallel with R10. Live product integration in R13 requires this
gate accepted.

## Acceptance

- versioned migrations
- PostgreSQL-capable repository interface plus SQLite fixture path
- R7 seed importer, reset, health, backup/export
- 100 users / 100 sessions survive process restart
- revoke removes a session from matches and aggregates with no stale leakage
- metadata permutation cannot change engine order or scores
- hidden users absent from service responses
- concurrent create/discover smoke
- existing engine/discovery tests remain green
