using Microsoft.Extensions.Diagnostics.HealthChecks;
using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Infrastructure.AnalysisCapture;
using ToxicAnalyzer.Infrastructure.Auth;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class StorageHealthCheckTests
{
    [Fact]
    public async Task AuthStorageHealthCheck_ReturnsHealthy_WhenConnectionOpens()
    {
        var healthCheck = new AuthStorageHealthCheck(new StubAuthDbConnectionFactory());

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Healthy, result.Status);
    }

    [Fact]
    public async Task AuthStorageHealthCheck_ReturnsUnhealthy_WhenConnectionFails()
    {
        var healthCheck = new AuthStorageHealthCheck(new StubAuthDbConnectionFactory(
            new NpgsqlException("auth down")));

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Unhealthy, result.Status);
        Assert.Contains("auth PostgreSQL", result.Description);
    }

    [Fact]
    public async Task AnalysisCaptureStorageHealthCheck_ReturnsHealthy_WhenDisabled()
    {
        var healthCheck = new AnalysisCaptureStorageHealthCheck(
            new StubAnalysisCaptureDbConnectionFactory(),
            Options.Create(new AnalysisCaptureOptions
            {
                Enabled = false,
                ConnectionString = "postgresql://user:pass@localhost:5432/app"
            }));

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Healthy, result.Status);
        Assert.Equal("Analysis capture storage is disabled.", result.Description);
    }

    [Fact]
    public async Task AnalysisCaptureStorageHealthCheck_ReturnsHealthy_WhenConnectionOpens()
    {
        var healthCheck = new AnalysisCaptureStorageHealthCheck(
            new StubAnalysisCaptureDbConnectionFactory(),
            Options.Create(new AnalysisCaptureOptions
            {
                Enabled = true,
                ConnectionString = "postgresql://user:pass@localhost:5432/app"
            }));

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Healthy, result.Status);
    }

    [Fact]
    public async Task AnalysisCaptureStorageHealthCheck_ReturnsUnhealthy_WhenConnectionFails()
    {
        var healthCheck = new AnalysisCaptureStorageHealthCheck(
            new StubAnalysisCaptureDbConnectionFactory(new NpgsqlException("capture down")),
            Options.Create(new AnalysisCaptureOptions
            {
                Enabled = true,
                ConnectionString = "postgresql://user:pass@localhost:5432/app"
            }));

        var result = await healthCheck.CheckHealthAsync(new HealthCheckContext(), CancellationToken.None);

        Assert.Equal(HealthStatus.Unhealthy, result.Status);
        Assert.Contains("analysis capture PostgreSQL", result.Description);
    }

    private sealed class StubAuthDbConnectionFactory : AuthDbConnectionFactory
    {
        private readonly Exception? _exception;

        public StubAuthDbConnectionFactory(Exception? exception = null)
            : base(Options.Create(new AuthOptions
            {
                Issuer = "issuer",
                Audience = "audience",
                SigningKey = "01234567890123456789012345678901",
                ConnectionString = "postgresql://user:pass@localhost:5432/app"
            }))
        {
            _exception = exception;
        }

        public override Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
        {
            if (_exception is not null)
            {
                return Task.FromException<NpgsqlConnection>(_exception);
            }

            return Task.FromResult(new NpgsqlConnection("Host=localhost;Username=user;Password=pass;Database=app"));
        }
    }

    private sealed class StubAnalysisCaptureDbConnectionFactory : AnalysisCaptureDbConnectionFactory
    {
        private readonly Exception? _exception;

        public StubAnalysisCaptureDbConnectionFactory(Exception? exception = null)
            : base(Options.Create(new AnalysisCaptureOptions
            {
                Enabled = true,
                ConnectionString = "postgresql://user:pass@localhost:5432/app"
            }))
        {
            _exception = exception;
        }

        public override Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
        {
            if (_exception is not null)
            {
                return Task.FromException<NpgsqlConnection>(_exception);
            }

            return Task.FromResult(new NpgsqlConnection("Host=localhost;Username=user;Password=pass;Database=app"));
        }
    }
}
