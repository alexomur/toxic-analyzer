using Microsoft.Extensions.Diagnostics.HealthChecks;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceHealthCheck : IHealthCheck
{
    private readonly HttpClient _httpClient;

    public ModelServiceHealthCheck(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<HealthCheckResult> CheckHealthAsync(
        HealthCheckContext context,
        CancellationToken cancellationToken = default)
    {
        try
        {
            using var response = await _httpClient.GetAsync(
                "health/ready",
                HttpCompletionOption.ResponseHeadersRead,
                cancellationToken);

            if (response.IsSuccessStatusCode)
            {
                return HealthCheckResult.Healthy();
            }

            return HealthCheckResult.Unhealthy(
                description: $"Model service readiness probe returned HTTP {(int)response.StatusCode} ({response.StatusCode}).");
        }
        catch (TaskCanceledException exception) when (!cancellationToken.IsCancellationRequested)
        {
            return HealthCheckResult.Unhealthy("Timed out while calling model service readiness probe.", exception);
        }
        catch (HttpRequestException exception)
        {
            return HealthCheckResult.Unhealthy("Failed to reach model service readiness probe.", exception);
        }
    }
}
