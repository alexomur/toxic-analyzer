using Microsoft.Extensions.Options;
using Npgsql;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class PostgresAnalysisCaptureStore : IAnalysisTextStore
{
    private readonly AnalysisCaptureDbConnectionFactory _connectionFactory;
    private readonly AnalysisCaptureSchemaInitializer _schemaInitializer;
    private readonly AnalysisCaptureOptions _options;

    public PostgresAnalysisCaptureStore(
        AnalysisCaptureDbConnectionFactory connectionFactory,
        AnalysisCaptureSchemaInitializer schemaInitializer,
        IOptions<AnalysisCaptureOptions> options)
    {
        _connectionFactory = connectionFactory;
        _schemaInitializer = schemaInitializer;
        _options = options.Value;
    }

    public async Task UpsertAsync(IReadOnlyList<AnalysisTextUpsertRecord> records, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(records);

        if (records.Count == 0)
        {
            return;
        }

        await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);

        await using var batch = new NpgsqlBatch(connection);

        foreach (var record in records)
        {
            var command = new NpgsqlBatchCommand(AnalysisCaptureSql.BuildUpsertSql(_options.Schema));
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
}
