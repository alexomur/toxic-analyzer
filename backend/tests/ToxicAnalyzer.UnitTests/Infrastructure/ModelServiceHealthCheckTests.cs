using System.Net;
using Microsoft.Extensions.Diagnostics.HealthChecks;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class ModelServiceHealthCheckTests
{
    [Fact]
    public async Task CheckHealthAsync_ReturnsHealthy_WhenModelServiceIsReady()
    {
        var healthCheck = CreateHealthCheck((request, cancellationToken) =>
        {
            Assert.Equal(HttpMethod.Get, request.Method);
            Assert.Equal("http://localhost:8000/health/ready", request.RequestUri?.ToString());
            return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK));
        });

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Healthy, result.Status);
    }

    [Fact]
    public async Task CheckHealthAsync_ReturnsUnhealthy_WhenModelServiceReturnsFailure()
    {
        var healthCheck = CreateHealthCheck((request, cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.ServiceUnavailable)));

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Unhealthy, result.Status);
        Assert.Contains("503", result.Description);
    }

    private static ModelServiceHealthCheck CreateHealthCheck(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handler)
    {
        var httpClient = new HttpClient(new StubHttpMessageHandler(handler))
        {
            BaseAddress = new Uri("http://localhost:8000/"),
            Timeout = TimeSpan.FromSeconds(10)
        };

        return new ModelServiceHealthCheck(httpClient);
    }

    private sealed class StubHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _handler;

        public StubHttpMessageHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return _handler(request, cancellationToken);
        }
    }
}
