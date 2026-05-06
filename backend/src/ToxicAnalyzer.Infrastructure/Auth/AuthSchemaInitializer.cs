using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class AuthSchemaInitializer
{
    private readonly AuthOptions _options;
    private readonly ILogger<AuthSchemaInitializer> _logger;
    private bool _schemaEnsured;

    public AuthSchemaInitializer(
        IOptions<AuthOptions> options,
        ILogger<AuthSchemaInitializer> logger)
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

        if (!AnalysisCapture.AnalysisCaptureOptions.IsValidSchema(_options.Schema))
        {
            throw new InvalidOperationException($"Invalid PostgreSQL schema name '{_options.Schema}'.");
        }

        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildEnsureSchemaSql(_options.Schema);
        command.Parameters.AddWithValue("admin_role", _options.AdminRole);
        await command.ExecuteNonQueryAsync(cancellationToken);

        _schemaEnsured = true;
        _logger.LogInformation("Auth schema is ready in PostgreSQL schema {Schema}.", _options.Schema);
    }
}
