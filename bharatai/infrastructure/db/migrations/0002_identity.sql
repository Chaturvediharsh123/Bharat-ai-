-- Migration 0002 — identity & access (users, audit_events).
-- Additive: introduces the Identity context. Does not alter any existing table.

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    role          TEXT NOT NULL,
    password_hash TEXT,                 -- NULL for OTP-only accounts; never plaintext
    status        TEXT NOT NULL,
    full_name     TEXT,
    phone         TEXT,
    citizen_id    TEXT REFERENCES citizen_profiles(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- ── audit_events (append-only) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
    id          TEXT PRIMARY KEY,
    actor_id    TEXT,
    action      TEXT NOT NULL,
    resource    TEXT,
    success     INTEGER NOT NULL DEFAULT 1,
    detail      TEXT,
    occurred_at TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_actor    ON audit_events(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_occurred ON audit_events(occurred_at);
