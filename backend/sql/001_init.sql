-- CalendAI PostgreSQL schema (aligned with Arthur's Sprint 1–2 DDL)
-- Additive columns: display_name, timezone on users; sync_logs for device sync audit.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    telegram_id BIGINT UNIQUE,
    password_hash VARCHAR(255),
    display_name VARCHAR(255),
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    subscription_tier VARCHAR(32) NOT NULL DEFAULT 'free',
    ai_requests_this_week INTEGER NOT NULL DEFAULT 0,
    week_reset_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_email ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);

CREATE TABLE IF NOT EXISTS events (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(512) NOT NULL,
    event_type VARCHAR(32) NOT NULL DEFAULT 'other',
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    location VARCHAR(255),
    teacher VARCHAR(255),
    description TEXT,
    recurrence_rule TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_event_time CHECK (end_time > start_time)
);

CREATE INDEX IF NOT EXISTS idx_events_user_updated ON events (user_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_events_user_start_time ON events (user_id, start_time);

-- Only bump updated_at when the client did not send its own timestamp.
-- A blind NOW() trigger would break Last-Write-Wins sync.
CREATE OR REPLACE FUNCTION update_events_modtime()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.updated_at IS NOT DISTINCT FROM OLD.updated_at THEN
        NEW.updated_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_events_modtime ON events;
CREATE TRIGGER trigger_update_events_modtime
BEFORE UPDATE ON events
FOR EACH ROW EXECUTE FUNCTION update_events_modtime();

CREATE TABLE IF NOT EXISTS sync_logs (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(36) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(128),
    last_sync_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    client_changes_count INTEGER NOT NULL DEFAULT 0,
    server_changes_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sync_logs_user_device UNIQUE (user_id, device_id)
);

CREATE INDEX IF NOT EXISTS ix_sync_logs_user_id ON sync_logs (user_id);
