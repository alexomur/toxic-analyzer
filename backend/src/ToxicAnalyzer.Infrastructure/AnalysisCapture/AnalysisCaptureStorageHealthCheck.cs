using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Options;
namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureStorageHealthCheck : IHealthCheck
{
    private readonly AnalysisCaptureDbConnectionFactory _connectionFactory;
    private readonly AnalysisCaptureOptions _options;

    public AnalysisCaptureStorageHealthCheck(
        AnalysisCaptureDbConnectionFactory connectionFactory,
        IOptions<AnalysisCaptureOptions> options)
    {
        _connectionFactory = connectionFactory;
        _options = options.Value;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        if (!_options.Enabled)
        {
            return HealthCheckResult.Healthy("Analysis capture storage is disabled.");
        }

        try
        {
            await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
            return HealthCheckResult.Healthy();
        }
        catch (Exception exception) when (exception is InvalidOperationException or Npgsql.NpgsqlException or TimeoutException)
        {
            return HealthCheckResult.Unhealthy("Failed to reach analysis capture PostgreSQL storage.", exception);
        }
    }
}
