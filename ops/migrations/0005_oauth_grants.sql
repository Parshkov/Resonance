-- resonance-persistence/0.5 OAuth grant store (post-release hardening)
-- Authorization codes, rotating refresh grants and dynamic client
-- registrations used to live in process memory, so every redeploy forced
-- hosted MCP clients to re-authorize. Records are opaque JSON written by
-- src/remote/oauth.py. They are not corpus content and never bump the
-- corpus generation. Keys are hashed by the writer where they are secrets.

CREATE TABLE IF NOT EXISTS oauth_grants (
    kind TEXT NOT NULL,
    grant_key TEXT NOT NULL,
    user_id TEXT,
    record_json TEXT NOT NULL,
    expires_at REAL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (kind, grant_key)
);

CREATE INDEX IF NOT EXISTS oauth_grants_user_idx ON oauth_grants (kind, user_id);
