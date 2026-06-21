-- Migration 0001 — initial BharatAI schema.
-- Seven tables map 1:1 to the seven persistable domain entities, plus schema_meta.
-- Column names mirror domain field names; storage-shape suffixes (_json, _paise) differ.

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ── citizen_profiles  ⇄  domain.CitizenProfile ──────────────────────────────
CREATE TABLE IF NOT EXISTS citizen_profiles (
    id                    TEXT PRIMARY KEY,
    full_name             TEXT,
    date_of_birth         TEXT,                 -- ISO-8601 date
    gender                TEXT,
    category              TEXT,
    marital_status        TEXT,
    annual_income_paise   INTEGER,              -- Money stored as integer paise
    occupation            TEXT,
    is_bpl                INTEGER,              -- 0/1/NULL
    disability_status     INTEGER NOT NULL DEFAULT 0,
    disability_percentage INTEGER,
    family_size           INTEGER,
    address_json          TEXT,                 -- Address value object as JSON
    state                 TEXT,                 -- denormalized from address for indexing
    district              TEXT,                 -- denormalized from address for indexing
    aadhaar_last4         TEXT,
    pan_masked            TEXT,
    mobile                TEXT,
    languages_json        TEXT,                 -- JSON array of strings
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_citizen_state          ON citizen_profiles(state);
CREATE INDEX IF NOT EXISTS idx_citizen_district       ON citizen_profiles(district);
CREATE INDEX IF NOT EXISTS idx_citizen_state_district ON citizen_profiles(state, district);

-- ── schemes  ⇄  domain.Scheme ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS schemes (
    id                       TEXT PRIMARY KEY,
    name                     TEXT NOT NULL,
    code                     TEXT,
    description              TEXT NOT NULL DEFAULT '',
    department               TEXT,
    level                    TEXT,
    state                    TEXT,              -- NULL == central / all-India
    category_tags_json       TEXT,
    eligibility_criteria_json TEXT NOT NULL,
    benefits_json            TEXT,
    application_window_json  TEXT,
    source_url               TEXT,
    verified_at              TEXT,
    is_active                INTEGER NOT NULL DEFAULT 1,
    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_scheme_code ON schemes(code) WHERE code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_scheme_state  ON schemes(state);
CREATE INDEX IF NOT EXISTS idx_scheme_active ON schemes(is_active);

-- ── eligibility_results  ⇄  domain.EligibilityResult (append-only) ───────────
CREATE TABLE IF NOT EXISTS eligibility_results (
    id                        TEXT PRIMARY KEY,
    citizen_id                TEXT NOT NULL REFERENCES citizen_profiles(id) ON DELETE CASCADE,
    scheme_id                 TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
    status                    TEXT NOT NULL,
    score                     REAL,
    confidence                REAL,
    evaluations_json          TEXT,
    missing_profile_fields_json TEXT,
    explanation               TEXT,
    evaluated_at              TEXT NOT NULL,
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_elig_citizen        ON eligibility_results(citizen_id);
CREATE INDEX IF NOT EXISTS idx_elig_citizen_scheme ON eligibility_results(citizen_id, scheme_id);

-- ── documents  ⇄  domain.DocumentRecord ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id                        TEXT PRIMARY KEY,
    citizen_id                TEXT NOT NULL REFERENCES citizen_profiles(id) ON DELETE CASCADE,
    doc_type                  TEXT NOT NULL,
    file_path                 TEXT,
    file_name                 TEXT,
    mime_type                 TEXT,
    file_size_bytes           INTEGER,
    checksum_sha256           TEXT,
    ocr_result_json           TEXT,
    extracted_name            TEXT,
    extracted_dob             TEXT,
    extracted_document_number TEXT,             -- MASKED
    issue_date                TEXT,
    expiry_date               TEXT,
    validation_status         TEXT NOT NULL,
    validation_errors_json    TEXT,
    confidence_score          REAL,
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doc_citizen      ON documents(citizen_id);
CREATE INDEX IF NOT EXISTS idx_doc_citizen_type ON documents(citizen_id, doc_type);
CREATE INDEX IF NOT EXISTS idx_doc_checksum     ON documents(checksum_sha256);

-- ── reminders  ⇄  domain.Reminder ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reminders (
    id          TEXT PRIMARY KEY,
    citizen_id  TEXT NOT NULL REFERENCES citizen_profiles(id) ON DELETE CASCADE,
    scheme_id   TEXT REFERENCES schemes(id) ON DELETE SET NULL,
    title       TEXT NOT NULL,
    description TEXT,
    due_date    TEXT,
    remind_at   TEXT,
    status      TEXT NOT NULL,
    channel     TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reminder_citizen ON reminders(citizen_id);
CREATE INDEX IF NOT EXISTS idx_reminder_due     ON reminders(due_date);
CREATE INDEX IF NOT EXISTS idx_reminder_status  ON reminders(status);

-- ── application_history  ⇄  domain.ApplicationHistoryEntry ───────────────────
CREATE TABLE IF NOT EXISTS application_history (
    id                TEXT PRIMARY KEY,
    citizen_id        TEXT NOT NULL REFERENCES citizen_profiles(id) ON DELETE CASCADE,
    scheme_id         TEXT NOT NULL REFERENCES schemes(id) ON DELETE CASCADE,
    status            TEXT NOT NULL,
    reference_id      TEXT,
    notes             TEXT,
    submitted_at      TEXT,
    updated_status_at TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_app_citizen        ON application_history(citizen_id);
CREATE INDEX IF NOT EXISTS idx_app_citizen_scheme ON application_history(citizen_id, scheme_id);
CREATE INDEX IF NOT EXISTS idx_app_status         ON application_history(status);
