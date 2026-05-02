using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Abstractions;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class PostgresAnalysisTextStore : IAnalysisTextStore, IAnalysisTextVotingRepository
{
    private readonly AnalysisCaptureOptions _options;
    private readonly ILogger<PostgresAnalysisTextStore> _logger;
    private readonly string _normalizedConnectionString;
    private bool _schemaEnsured;

    public PostgresAnalysisTextStore(
        IOptions<AnalysisCaptureOptions> options,
        ILogger<PostgresAnalysisTextStore> logger)
    {
        _options = options.Value;
        _logger = logger;
        _normalizedConnectionString = AnalysisCaptureConnectionString.Normalize(_options.ConnectionString);
    }

    public async Task UpsertAsync(IReadOnlyList<AnalysisTextUpsertRecord> records, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(records);

        if (records.Count == 0)
        {
            return;
        }

        await using var connection = new NpgsqlConnection(_normalizedConnectionString);
        await connection.OpenAsync(cancellationToken);

        if (!_schemaEnsured)
        {
            await EnsureSchemaAsync(connection, cancellationToken);
            _schemaEnsured = true;
        }

        await using var batch = new NpgsqlBatch(connection);

        foreach (var record in records)
        {
            var command = new NpgsqlBatchCommand(BuildUpsertSql(_options.Schema));
            command.Parameters.AddWithValue("id", record.Id);
            command.Parameters.AddWithValue("text_fingerprint", record.TextFingerprint);
            command.Parameters.AddWithValue("normalized_text", record.NormalizedText);
            command.Parameters.AddWithValue("text_length", record.TextLength);
            command.Parameters.AddWithValue("request_count", record.RequestCount);
            command.Parameters.AddWithValue("last_label", record.LastLabel);
            command.Parameters.AddWithValue("last_toxic_probability", Convert.ToDouble(record.LastToxicProbability));
            command.Parameters.AddWithValue("last_model_key", record.LastModelKey);
            command.Parameters.AddWithValue("last_model_version", record.LastModelVersion);
            command.Parameters.AddWithValue("source_kind", record.SourceKind);
            command.Parameters.AddWithValue("actor_id", (object?)record.ActorId ?? DBNull.Value);
            command.Parameters.AddWithValue("tenant_id", (object?)record.TenantId ?? DBNull.Value);
            command.Parameters.AddWithValue("created_at", record.CreatedAt);
            command.Parameters.AddWithValue("last_seen_at", record.LastSeenAt);
            batch.BatchCommands.Add(command);
        }

        await batch.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken)
    {
        await using var connection = new NpgsqlConnection(_normalizedConnectionString);
        await connection.OpenAsync(cancellationToken);
        await EnsureSchemaReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetRandomSql(_options.Schema);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);

        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new AnalysisTextVotingCandidate(
            reader.GetGuid(0),
            reader.GetString(1));
    }

    public async Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
    {
        await using var connection = new NpgsqlConnection(_normalizedConnectionString);
        await connection.OpenAsync(cancellationToken);
        await EnsureSchemaReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetByIdSql(_options.Schema);
        command.Parameters.AddWithValue("id", id);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);

        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new AnalysisTextVotingDetails(
            reader.GetGuid(0),
            reader.GetString(1),
            reader.GetInt32(2),
            reader.GetInt64(3),
            reader.GetInt16(4),
            Convert.ToDecimal(reader.GetValue(5)),
            reader.GetString(6),
            reader.GetString(7),
            reader.GetInt32(8),
            reader.GetInt32(9),
            reader.GetFieldValue<DateTimeOffset>(10),
            reader.GetFieldValue<DateTimeOffset>(11));
    }

    public async Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CurrentActor actor, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(actor);

        await using var connection = new NpgsqlConnection(_normalizedConnectionString);
        await connection.OpenAsync(cancellationToken);
        await EnsureSchemaReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = BuildRegisterVoteSql(_options.Schema);
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("actor_key", actor.ActorKey);
        command.Parameters.AddWithValue("actor_type", actor.ActorType.ToString().ToLowerInvariant());
        command.Parameters.AddWithValue("actor_id", actor.SubjectId);
        command.Parameters.AddWithValue("tenant_id", (object?)actor.TenantId ?? DBNull.Value);
        command.Parameters.AddWithValue("source_kind", actor.SourceKind);
        command.Parameters.AddWithValue("vote", (short)vote);
        command.Parameters.AddWithValue("created_at", DateTimeOffset.UtcNow);
        command.Parameters.AddWithValue("updated_at", DateTimeOffset.UtcNow);

        var rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
        return rowsAffected > 0;
    }

    private async Task EnsureSchemaAsync(NpgsqlConnection connection, CancellationToken cancellationToken)
    {
        if (!AnalysisCaptureOptions.IsValidSchema(_options.Schema))
        {
            throw new InvalidOperationException($"Invalid PostgreSQL schema name '{_options.Schema}'.");
        }

        await using var command = connection.CreateCommand();
        command.CommandText = BuildEnsureSchemaSql(_options.Schema);
        await command.ExecuteNonQueryAsync(cancellationToken);

        _logger.LogInformation("Analysis capture schema is ready in PostgreSQL schema {Schema}.", _options.Schema);
    }

    private async Task EnsureSchemaReadyAsync(NpgsqlConnection connection, CancellationToken cancellationToken)
    {
        if (_schemaEnsured)
        {
            return;
        }

        await EnsureSchemaAsync(connection, cancellationToken);
        _schemaEnsured = true;
    }

    private static string BuildEnsureSchemaSql(string schema)
    {
        return $$"""
        CREATE SCHEMA IF NOT EXISTS {{schema}};

        CREATE TABLE IF NOT EXISTS {{schema}}.analysis_texts (
            id UUID PRIMARY KEY,
            text_fingerprint TEXT NOT NULL UNIQUE,
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
        """;
    }

    private static string BuildGetRandomSql(string schema)
    {
        return $$"""
        WITH vote_totals AS (
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_votes
            GROUP BY text_id
        )
        SELECT
            text.id,
            text.normalized_text
        FROM {{schema}}.analysis_texts AS text
        LEFT JOIN vote_totals ON vote_totals.text_id = text.id
        ORDER BY (-LN(GREATEST(random(), 1e-12)) * (COALESCE(vote_totals.votes_toxic, 0) + COALESCE(vote_totals.votes_non_toxic, 0) + 1))
        LIMIT 1;
        """;
    }

    private static string BuildRegisterVoteSql(string schema)
    {
        return $$"""
        INSERT INTO {{schema}}.analysis_text_votes (
            text_id,
            actor_key,
            actor_type,
            actor_id,
            tenant_id,
            source_kind,
            vote,
            created_at,
            updated_at
        )
        SELECT
            text.id,
            @actor_key,
            @actor_type,
            @actor_id,
            @tenant_id,
            @source_kind,
            @vote,
            @created_at,
            @updated_at
        FROM {{schema}}.analysis_texts AS text
        WHERE text.id = @id
        ON CONFLICT (text_id, actor_key) DO UPDATE
        SET
            vote = EXCLUDED.vote,
            tenant_id = EXCLUDED.tenant_id,
            source_kind = EXCLUDED.source_kind,
            updated_at = EXCLUDED.updated_at;
        """;
    }

    private static string BuildGetByIdSql(string schema)
    {
        return $$"""
        WITH vote_totals AS (
            SELECT
                text_id,
                COUNT(*) FILTER (WHERE vote = 1) AS votes_toxic,
                COUNT(*) FILTER (WHERE vote = 0) AS votes_non_toxic
            FROM {{schema}}.analysis_text_votes
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
            COALESCE(vote_totals.votes_toxic, 0) AS votes_toxic,
            COALESCE(vote_totals.votes_non_toxic, 0) AS votes_non_toxic,
            text.created_at,
            text.last_seen_at
        FROM {{schema}}.analysis_texts AS text
        LEFT JOIN vote_totals ON vote_totals.text_id = text.id
        WHERE text.id = @id;
        """;
    }

    private static string BuildUpsertSql(string schema)
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
        ON CONFLICT (text_fingerprint) DO UPDATE
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
}
