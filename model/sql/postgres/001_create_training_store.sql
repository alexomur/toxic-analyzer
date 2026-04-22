CREATE SCHEMA IF NOT EXISTS {{SCHEMA}};

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.canonical_training_texts (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_comment_id TEXT,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    text_length INTEGER NOT NULL CHECK (text_length >= 0),
    label SMALLINT NOT NULL CHECK (label IN (0, 1)),
    label_status TEXT NOT NULL DEFAULT 'labeled'
        CHECK (label_status IN ('labeled', 'archived')),
    source_labels TEXT,
    origin_system TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (origin_system, source, source_record_id)
);

CREATE INDEX IF NOT EXISTS idx_canonical_training_texts_source
    ON {{SCHEMA}}.canonical_training_texts (source);

CREATE INDEX IF NOT EXISTS idx_canonical_training_texts_label_status
    ON {{SCHEMA}}.canonical_training_texts (label_status);

CREATE INDEX IF NOT EXISTS idx_canonical_training_texts_label
    ON {{SCHEMA}}.canonical_training_texts (label);

CREATE INDEX IF NOT EXISTS idx_canonical_training_texts_origin_system
    ON {{SCHEMA}}.canonical_training_texts (origin_system);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.feedback_events (
    id BIGSERIAL PRIMARY KEY,
    feedback_source TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    text_length INTEGER NOT NULL CHECK (text_length >= 0),
    predicted_label SMALLINT CHECK (predicted_label IN (0, 1)),
    predicted_score DOUBLE PRECISION
        CHECK (predicted_score IS NULL OR (predicted_score >= 0.0 AND predicted_score <= 1.0)),
    feedback_label SMALLINT CHECK (feedback_label IN (0, 1)),
    feedback_reason TEXT,
    model_key TEXT,
    event_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_events_feedback_source
    ON {{SCHEMA}}.feedback_events (feedback_source);

CREATE INDEX IF NOT EXISTS idx_feedback_events_created_at
    ON {{SCHEMA}}.feedback_events (created_at);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.training_candidates (
    id BIGSERIAL PRIMARY KEY,
    feedback_event_id BIGINT
        REFERENCES {{SCHEMA}}.feedback_events (id)
        ON DELETE SET NULL,
    source TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    text_length INTEGER NOT NULL CHECK (text_length >= 0),
    proposed_label SMALLINT CHECK (proposed_label IN (0, 1)),
    approved_label SMALLINT CHECK (approved_label IN (0, 1)),
    candidate_status TEXT NOT NULL DEFAULT 'pending_review'
        CHECK (candidate_status IN ('pending_review', 'approved', 'rejected', 'promoted')),
    review_notes TEXT,
    canonical_text_id BIGINT
        REFERENCES {{SCHEMA}}.canonical_training_texts (id)
        ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    promoted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_training_candidates_status
    ON {{SCHEMA}}.training_candidates (candidate_status);

CREATE INDEX IF NOT EXISTS idx_training_candidates_source
    ON {{SCHEMA}}.training_candidates (source);

CREATE INDEX IF NOT EXISTS idx_training_candidates_feedback_event
    ON {{SCHEMA}}.training_candidates (feedback_event_id);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.model_registry (
    id BIGSERIAL PRIMARY KEY,
    model_key TEXT NOT NULL UNIQUE,
    model_family TEXT NOT NULL DEFAULT 'baseline',
    model_version TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    artifact_storage TEXT NOT NULL DEFAULT 'local_artifact'
        CHECK (artifact_storage IN ('local_artifact')),
    artifact_sha256 TEXT,
    training_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'ready'
        CHECK (status IN ('training', 'ready', 'failed', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trained_at TIMESTAMPTZ,
    promoted_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_model_registry_status
    ON {{SCHEMA}}.model_registry (status);

CREATE TABLE IF NOT EXISTS {{SCHEMA}}.retrain_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_key TEXT NOT NULL UNIQUE,
    job_type TEXT NOT NULL DEFAULT 'retrain'
        CHECK (job_type IN ('train', 'retrain')),
    trigger_type TEXT NOT NULL
        CHECK (trigger_type IN ('manual', 'scheduled', 'feedback_threshold', 'backfill')),
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    requested_by TEXT,
    output_model_id BIGINT
        REFERENCES {{SCHEMA}}.model_registry (id)
        ON DELETE SET NULL,
    dataset_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    job_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_retrain_jobs_status
    ON {{SCHEMA}}.retrain_jobs (status);

CREATE INDEX IF NOT EXISTS idx_retrain_jobs_created_at
    ON {{SCHEMA}}.retrain_jobs (created_at);
