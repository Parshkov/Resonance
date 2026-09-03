-- resonance-persistence/0.3 collaboration migration (R14)
-- Adds the request message and lifecycle timestamps to the dormant intro
-- table. Collaboration writes never touch the corpus generation: connection
-- state is not discoverable corpus content.

ALTER TABLE intros ADD COLUMN message TEXT NOT NULL DEFAULT '';
ALTER TABLE intros ADD COLUMN from_user_id TEXT NOT NULL DEFAULT '';
ALTER TABLE intros ADD COLUMN to_user_id TEXT NOT NULL DEFAULT '';
ALTER TABLE intros ADD COLUMN cancelled_at TEXT;
ALTER TABLE intros ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS idx_intros_from_user ON intros(from_user_id);
CREATE INDEX IF NOT EXISTS idx_intros_to_user ON intros(to_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel_id, created_at);
