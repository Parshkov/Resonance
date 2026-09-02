# R11 Persistence

Durable multi-user product store for Resonance. The accepted structural
engine is unchanged. JSONL under `demo/corpus/` remains a deterministic
seed/replay fixture, not the live database.

## Backends

- SQLite file: default for tests, judge reset, and local demo.
- PostgreSQL: hosted-pilot backend. Set `RESONANCE_DATABASE_URL=postgres://...`
  and install `psycopg`. The repository interface is identical.

## Product records

- users / pseudonymous profiles
- sessions
- validated Thought DNA JSON + schema/version + content hash
- per-session consent/share flags
- optional display profile
- coarse consented/synthetic location
- created/updated/revoked/deleted timestamps
- audit events
- empty `intros` / `channels` / `messages` tables reserved for R14

## Hard rules

- Invalid Thought DNA is never discoverable.
- Hidden, revoked, or deleted sessions are omitted from the engine index,
  discovery responses, and aggregation buckets.
- Location / display / domain metadata cannot change engine order or scores.
- Rebuild from DB is deterministic (sorted `thought_id`).
- Raw private conversation text is not required; structured Thought DNA plus
  provenance is enough.

## Commands

```bash
python3 -m src.persistence.cli --db var/resonance-pilot.sqlite migrate
python3 -m src.persistence.cli --db var/resonance-pilot.sqlite seed-r7
python3 -m src.persistence.cli --db var/resonance-pilot.sqlite health
python3 -m src.persistence.cli --db var/resonance-pilot.sqlite export --out var/backup.json
python3 -m src.persistence.cli --db var/resonance-pilot.sqlite reset
```

Transport adapters (WebMCP, stdio MCP, remote MCP) should call
`LiveCorpusService` methods rather than reimplementing storage or matching.
