using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class PostgresAnalysisTextStore : IAnalysisTextStore
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
            votes_total INTEGER NOT NULL DEFAULT 0 CHECK (votes_total >= 0),
            votes_toxic INTEGER NOT NULL DEFAULT 0 CHECK (votes_toxic >= 0),
            votes_non_toxic INTEGER NOT NULL DEFAULT 0 CHECK (votes_non_toxic >= 0),
            created_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            CHECK (votes_total = votes_toxic + votes_non_toxic)
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_texts_last_seen_at
            ON {{schema}}.analysis_texts (last_seen_at DESC);

        CREATE INDEX IF NOT EXISTS idx_analysis_texts_last_label
            ON {{schema}}.analysis_texts (last_label);
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
