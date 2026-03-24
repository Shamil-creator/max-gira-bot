BEGIN;

CREATE TABLE IF NOT EXISTS bot_drafts (
    draft_key TEXT PRIMARY KEY,
    scalar_value TEXT NULL,
    list_value JSONB NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bot_drafts_updated_at
    ON bot_drafts(updated_at);

COMMIT;
