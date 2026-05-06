using Microsoft.Extensions.Diagnostics.HealthChecks;
namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class AuthStorageHealthCheck : IHealthCheck
{
    private readonly AuthDbConnectionFactory _connectionFactory;

    public AuthStorageHealthCheck(AuthDbConnectionFactory connectionFactory)
    {
        _connectionFactory = connectionFactory;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            await using var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
            return HealthCheckResult.Healthy();
        }
        catch (Exception exception) when (exception is InvalidOperationException or Npgsql.NpgsqlException or TimeoutException)
        {
            return HealthCheckResult.Unhealthy("Failed to reach auth PostgreSQL storage.", exception);
        }
    }
}
