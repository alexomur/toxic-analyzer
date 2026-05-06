using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureSchemaInitializer
{
    private readonly AnalysisCaptureOptions _options;
    private readonly ILogger<AnalysisCaptureSchemaInitializer> _logger;
    private bool _schemaEnsured;

    public AnalysisCaptureSchemaInitializer(
        IOptions<AnalysisCaptureOptions> options,
        ILogger<AnalysisCaptureSchemaInitializer> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public async Task EnsureReadyAsync(NpgsqlConnection connection, CancellationToken cancellationToken)
    {
        if (_schemaEnsured)
        {
            return;
        }

        if (!AnalysisCaptureOptions.IsValidSchema(_options.Schema))
        {
            throw new InvalidOperationException($"Invalid PostgreSQL schema name '{_options.Schema}'.");
        }

        await using var command = connection.CreateCommand();
        command.CommandText = AnalysisCaptureSql.BuildEnsureSchemaSql(_options.Schema);
        await command.ExecuteNonQueryAsync(cancellationToken);

        _schemaEnsured = true;
        _logger.LogInformation("Analysis capture schema is ready in PostgreSQL schema {Schema}.", _options.Schema);
    }
}
