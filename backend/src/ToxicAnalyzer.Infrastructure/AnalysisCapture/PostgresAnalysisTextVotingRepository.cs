using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Abstractions;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class PostgresAnalysisTextVotingRepository : IAnalysisTextVotingRepository
{
    private const string RandomPoolOrigin = "random_pool";

    private readonly AnalysisCaptureDbConnectionFactory _connectionFactory;
    private readonly AnalysisCaptureSchemaInitializer _schemaInitializer;
    private readonly AnalysisCaptureOptions _options;

    public PostgresAnalysisTextVotingRepository(
        AnalysisCaptureDbConnectionFactory connectionFactory,
        AnalysisCaptureSchemaInitializer schemaInitializer,
        IOptions<AnalysisCaptureOptions> options)
    {
        _connectionFactory = connectionFactory;
        _schemaInitializer = schemaInitializer;
        _options = options.Value;
    }

    public async Task<Guid?> EnsureVoteableTextAsync(
        Domain.Analysis.ToxicityAnalysis analysis,
        AnalysisTextOrigin origin,
        CurrentActor actor,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentNullException.ThrowIfNull(actor);

        await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = AnalysisCaptureSql.BuildEnsureVoteableTextSql(_options.Schema);
        command.Parameters.AddWithValue("id", analysis.Id.Value);
        command.Parameters.AddWithValue("text_fingerprint", analysis.TextFingerprint.Value);
        command.Parameters.AddWithValue("normalized_text", analysis.Text.Normalized);
        command.Parameters.AddWithValue("text_length", analysis.Text.Normalized.Length);
        command.Parameters.AddWithValue("request_count", 1L);
        command.Parameters.AddWithValue("last_label", (short)analysis.Label.Value);
        command.Parameters.AddWithValue("last_toxic_probability", Convert.ToDouble(analysis.ToxicProbability.Value));
        command.Parameters.AddWithValue("last_model_key", analysis.Model.ModelKey);
        command.Parameters.AddWithValue("last_model_version", analysis.Model.ModelVersion);
        command.Parameters.AddWithValue("origin_kind", origin.ToStorageValue());
        command.Parameters.AddWithValue("actor_id", actor.SubjectId);
        command.Parameters.AddWithValue("tenant_id", (object?)actor.TenantId ?? DBNull.Value);
        command.Parameters.AddWithValue("created_at", analysis.CreatedAt);
        command.Parameters.AddWithValue("last_seen_at", analysis.CreatedAt);

        var result = await command.ExecuteScalarAsync(cancellationToken);
        return result is Guid id ? id : result is string value && Guid.TryParse(value, out var parsed) ? parsed : null;
    }

    public async Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken)
    {
        await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetRandomSql(_options.Schema);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        return new AnalysisTextVotingCandidate(reader.GetGuid(0), reader.GetString(1));
    }

    public async Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
    {
        await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = AnalysisCaptureSql.BuildGetByIdSql(_options.Schema);
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

        await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);

        await using var command = connection.CreateCommand();
        command.CommandText = AnalysisCaptureSql.BuildRegisterVoteSql(_options.Schema);
        command.Parameters.AddWithValue("event_id", Guid.NewGuid());
        command.Parameters.AddWithValue("id", id);
        command.Parameters.AddWithValue("actor_key", actor.ActorKey);
        command.Parameters.AddWithValue("actor_type", actor.ActorType.ToString().ToLowerInvariant());
        command.Parameters.AddWithValue("actor_id", actor.SubjectId);
        command.Parameters.AddWithValue("tenant_id", (object?)actor.TenantId ?? DBNull.Value);
        command.Parameters.AddWithValue("source_kind", actor.SourceKind);
        command.Parameters.AddWithValue("vote", (short)vote);
        command.Parameters.AddWithValue("created_at", DateTimeOffset.UtcNow);

        var rowsAffected = await command.ExecuteNonQueryAsync(cancellationToken);
        return rowsAffected > 0;
    }

    internal static string BuildGetRandomSql(string schema)
    {
        return AnalysisCaptureSql.BuildGetRandomSql(schema, RandomPoolOrigin);
    }
}
