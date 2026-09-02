-- resonance-persistence/0.2 recovery migration
-- Adds fail-closed DB<->serving generation, optimistic session versions,
-- and durable idempotency records for agent/client retries.

ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS persistence_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    corpus_generation INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);

INSERT INTO persistence_state(state_id, corpus_generation, updated_at)
VALUES (1, 0, '')
ON CONFLICT(state_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS idempotency_keys (
    request_id TEXT PRIMARY KEY,
    operation TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_idempotency_created
    ON idempotency_keys(created_at);
