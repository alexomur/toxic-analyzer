namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

internal static class AnalysisCaptureSql
{
    public static string BuildEnsureSchemaSql(string schema)
    {
        return $$"""
        CREATE SCHEMA IF NOT EXISTS {{schema}};

        CREATE TABLE IF NOT EXISTS {{schema}}.analysis_texts (
            id UUID PRIMARY KEY,
            text_fingerprint TEXT NOT NULL,
            normalized_text TEXT NOT NULL,
            text_length INTEGER NOT NULL CHECK (text_length >= 0),
            request_count BIGINT NOT NULL CHECK (request_count >= 1),
            last_label SMALLINT NOT NULL CHECK (last_label IN (0, 1)),
            last_toxic_probability DOUBLE PRECISION NOT NULL
                CHECK (last_toxic_probability >= 0.0 AND last_toxic_probability <= 1.0),
            last_model_key TEXT NOT NULL,
            last_model_version TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            actor_id TEXT,
            tenant_id TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL
        );

        ALTER TABLE {{schema}}.analysis_texts
            DROP CONSTRAINT IF EXISTS analysis_texts_text_fingerprint_key;

        CREATE UNIQUE INDEX IF NOT EXISTS ux_analysis_texts_fingerprint_source_kind
            ON {{schema}}.analysis_texts (text_fingerprint, source_kind);

        CREATE TABLE IF NOT EXISTS {{schema}}.analysis_text_votes (
            text_id UUID NOT NULL REFERENCES {{schema}}.analysis_texts (id) ON DELETE CASCADE,
            actor_key TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            tenant_id TEXT,
            source_kind TEXT NOT NULL,
            vote SMALLINT NOT NULL CHECK (vote IN (0, 1)),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (text_id, actor_key)
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_texts_last_seen_at
            ON {{schema}}.analysis_texts (last_seen_at DESC);

        CREATE INDEX IF NOT EXISTS idx_analysis_texts_last_label
            ON {{schema}}.analysis_texts (last_label);

        CREATE INDEX IF NOT EXISTS idx_analysis_text_votes_text_id
            ON {{schema}}.analysis_text_votes (text_id);

        CREATE TABLE IF NOT EXISTS {{schema}}.analysis_text_vote_events (
            id UUID PRIMARY KEY,
            text_id UUID NOT NULL REFERENCES {{schema}}.analysis_texts (id) ON DELETE CASCADE,
            actor_key TEXT NOT NULL,
            actor_type TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            tenant_id TEXT,
            source_kind TEXT NOT NULL,
            vote SMALLINT NOT NULL CHECK (vote IN (0, 1)),
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_text_vote_events_text_id
            ON {{schema}}.analysis_text_vote_events (text_id);
        """;
    }

    public static string BuildUpsertSql(string schema)
    {
        return $$"""
        INSERT INTO {{schema}}.analysis_texts (
            id,
            text_fingerprint,
            normalized_text,
            text_length,
            request_count,
            last_label,
            last_toxic_probability,
            last_model_key,
            last_model_version,
            source_kind,
            actor_id,
            tenant_id,
            created_at,
            last_seen_at
        )
        VALUES (
            @id,
            @text_fingerprint,
            @normalized_text,
            @text_length,
            @request_count,
            @last_label,
            @last_toxic_probability,
            @last_model_key,
            @last_model_version,
            @source_kind,
            @actor_id,
            @tenant_id,
            @created_at,
            @last_seen_at
        )
        ON CONFLICT (text_fingerprint, source_kind) DO UPDATE
        SET
            request_count = {{schema}}.analysis_texts.request_count + EXCLUDED.request_count,
            last_label = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_label
                ELSE {{schema}}.analysis_texts.last_label
            END,
            last_toxic_probability = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_toxic_probability
                ELSE {{schema}}.analysis_texts.last_toxic_probability
            END,
            last_model_key = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_model_key
                ELSE {{schema}}.analysis_texts.last_model_key
            END,
            last_model_version = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_model_version
                ELSE {{schema}}.analysis_texts.last_model_version
            END,
            source_kind = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.source_kind
                ELSE {{schema}}.analysis_texts.source_kind
            END,
            actor_id = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.actor_id
                ELSE {{schema}}.analysis_texts.actor_id
            END,
            tenant_id = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.tenant_id
                ELSE {{schema}}.analysis_texts.tenant_id
            END,
            last_seen_at = GREATEST({{schema}}.analysis_texts.last_seen_at, EXCLUDED.last_seen_at);
        """;
    }

    public static string BuildEnsureVoteableTextSql(string schema)
    {
        return $$"""
        INSERT INTO {{schema}}.analysis_texts (
            id,
            text_fingerprint,
            normalized_text,
            text_length,
            request_count,
            last_label,
            last_toxic_probability,
            last_model_key,
            last_model_version,
            source_kind,
            actor_id,
            tenant_id,
            created_at,
            last_seen_at
        )
        VALUES (
            @id,
            @text_fingerprint,
            @normalized_text,
            @text_length,
            @request_count,
            @last_label,
            @last_toxic_probability,
            @last_model_key,
            @last_model_version,
            @origin_kind,
            @actor_id,
            @tenant_id,
            @created_at,
            @last_seen_at
        )
        ON CONFLICT (text_fingerprint, source_kind) DO UPDATE
        SET
            request_count = {{schema}}.analysis_texts.request_count + EXCLUDED.request_count,
            last_label = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_label
                ELSE {{schema}}.analysis_texts.last_label
            END,
            last_toxic_probability = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_toxic_probability
                ELSE {{schema}}.analysis_texts.last_toxic_probability
            END,
            last_model_key = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_model_key
                ELSE {{schema}}.analysis_texts.last_model_key
            END,
            last_model_version = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.last_model_version
                ELSE {{schema}}.analysis_texts.last_model_version
            END,
            actor_id = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.actor_id
                ELSE {{schema}}.analysis_texts.actor_id
            END,
            tenant_id = CASE
                WHEN EXCLUDED.last_seen_at >= {{schema}}.analysis_texts.last_seen_at THEN EXCLUDED.tenant_id
                ELSE {{schema}}.analysis_texts.tenant_id
            END,
            last_seen_at = GREATEST({{schema}}.analysis_texts.last_seen_at, EXCLUDED.last_seen_at)
        RETURNING id;
        """;
    }

    public static string BuildGetRandomSql(string schema, string randomPoolOrigin)
    {
        return $$"""
        WITH vote_totals AS (
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_votes
            GROUP BY text_id
            UNION ALL
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_vote_events
            GROUP BY text_id
        )
        SELECT
            text.id,
            text.normalized_text
        FROM {{schema}}.analysis_texts AS text
        LEFT JOIN (
            SELECT
                text_id,
                SUM(votes_toxic) AS votes_toxic,
                SUM(votes_non_toxic) AS votes_non_toxic
            FROM vote_totals
            GROUP BY text_id
        ) AS vote_totals ON vote_totals.text_id = text.id
        WHERE text.source_kind IN (
            '{{randomPoolOrigin}}',
            'bot_submitted')
        ORDER BY (-LN(GREATEST(random(), 1e-12)) * (COALESCE(vote_totals.votes_toxic, 0) + COALESCE(vote_totals.votes_non_toxic, 0) + 1))
        LIMIT 1;
        """;
    }

    public static string BuildGetByIdSql(string schema)
    {
        return $$"""
        WITH vote_totals AS (
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_votes
            GROUP BY text_id
            UNION ALL
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_vote_events
            GROUP BY text_id
        )
        SELECT
            text.id,
            text.normalized_text,
            text.text_length,
            text.request_count,
            text.last_label,
            text.last_toxic_probability,
            text.last_model_key,
            text.last_model_version,
            COALESCE(SUM(vote_totals.votes_toxic), 0) AS votes_toxic,
            COALESCE(SUM(vote_totals.votes_non_toxic), 0) AS votes_non_toxic,
            text.created_at,
            text.last_seen_at
        FROM {{schema}}.analysis_texts AS text
        LEFT JOIN vote_totals ON vote_totals.text_id = text.id
        WHERE text.id = @id
        GROUP BY
            text.id,
            text.normalized_text,
            text.text_length,
            text.request_count,
            text.last_label,
            text.last_toxic_probability,
            text.last_model_key,
            text.last_model_version,
            text.created_at,
            text.last_seen_at;
        """;
    }

    public static string BuildRegisterVoteSql(string schema)
    {
        return $$"""
        INSERT INTO {{schema}}.analysis_text_vote_events (
            id,
            text_id,
            actor_key,
            actor_type,
            actor_id,
            tenant_id,
            source_kind,
            vote,
            created_at
        )
        SELECT
            @event_id,
            text.id,
            @actor_key,
            @actor_type,
            @actor_id,
            @tenant_id,
            @source_kind,
            @vote,
            @created_at
        FROM {{schema}}.analysis_texts AS text
        WHERE text.id = @id;
        """;
    }
}
