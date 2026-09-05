-- resonance-persistence/0.6 shared topics
--
-- Two people introduced by Resonance do not talk to each other directly: each
-- talks to their own assistant, and the assistants meet here. Relaying prose
-- through two language models would waste the one thing an assistant is good
-- at — explaining a stranger's idea in its own person's terms — and would let
-- the meaning drift a little on every hop.
--
-- So what is stored is not a transcript. Each side contributes the STRUCTURE of
-- what it now understands, and the shared topic is what those structures say
-- together: where they agree, and — more usefully — where they contradict each
-- other. A contribution is append-only, so the topic has a history rather than
-- a current state somebody overwrote.
--
-- A contribution carries a small causal graph and a short note its author
-- approved. The raw conversation is never sent here and never stored, exactly
-- as for a shared thought.

CREATE TABLE IF NOT EXISTS workspace_contributions (
    contribution_id  TEXT PRIMARY KEY,
    workspace_id     TEXT NOT NULL,
    author_user_id   TEXT NOT NULL,
    thought_dna_json TEXT NOT NULL,
    note             TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

-- Read in (created_at, contribution_id) order: a reader's cursor is the last
-- contribution they were shown, so each side pulls only what is new to it and
-- nobody replays the history to catch up.
CREATE INDEX IF NOT EXISTS workspace_contributions_order_idx
    ON workspace_contributions (workspace_id, created_at, contribution_id);

CREATE INDEX IF NOT EXISTS workspace_contributions_author_idx
    ON workspace_contributions (workspace_id, author_user_id);
