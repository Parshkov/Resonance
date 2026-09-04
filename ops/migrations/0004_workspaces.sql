-- resonance-persistence/0.4 workspaces migration (R14B)
-- Multi-person idea rooms bootstrapped from an accepted R14 intro. Workspace
-- state is not discoverable corpus content, so no workspace write bumps the
-- corpus generation. Ids are opaque and membership is participant-only.

CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    brief TEXT NOT NULL DEFAULT '',
    owner_user_id TEXT NOT NULL,
    origin_intro_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS workspace_members (
    workspace_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    state TEXT NOT NULL,
    invited_by TEXT,
    invited_at TEXT NOT NULL,
    joined_at TEXT,
    PRIMARY KEY (workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS workspace_notes (
    note_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    author_user_id TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_tasks (
    task_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_artifacts (
    artifact_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    label TEXT NOT NULL,
    kind TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    added_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_links (
    link_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    why TEXT NOT NULL,
    linked_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workspace_activity (
    activity_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ws_members_user ON workspace_members(user_id);
CREATE INDEX IF NOT EXISTS idx_ws_notes_ws ON workspace_notes(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ws_tasks_ws ON workspace_tasks(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ws_activity_ws ON workspace_activity(workspace_id, created_at);
