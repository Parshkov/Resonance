-- resonance-persistence/0.1
-- Derived from superseded R11 PR #95 (Grok 4.6); preserved verbatim in shape
-- so databases created by that foundation upgrade through 0002 safely.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_label TEXT NOT NULL,
    avatar_placeholder TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    thought_id TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL,
    thought_dna TEXT NOT NULL,
    thought_dna_sha256 TEXT NOT NULL,
    thought_dna_schema_version TEXT NOT NULL,
    share_enabled INTEGER NOT NULL,
    share_thought_dna INTEGER NOT NULL,
    share_coarse_location INTEGER NOT NULL,
    share_display_profile INTEGER NOT NULL,
    location_json TEXT NOT NULL,
    presentation_json TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    builder_id TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    revoked_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_live_discoverable
    ON sessions(share_enabled, share_thought_dna, revoked_at, deleted_at);
CREATE INDEX IF NOT EXISTS idx_sessions_thought ON sessions(thought_id);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);

CREATE TABLE IF NOT EXISTS intros (
    intro_id TEXT PRIMARY KEY,
    from_session_id TEXT,
    to_session_id TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    accepted_at TEXT,
    declined_at TEXT
);

CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    intro_id TEXT,
    created_at TEXT NOT NULL,
    closed_at TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    channel_id TEXT,
    author_user_id TEXT,
    body TEXT,
    created_at TEXT NOT NULL
);
