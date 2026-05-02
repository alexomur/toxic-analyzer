using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class DevelopmentAdminBootstrapHostedService : IHostedService
{
    private readonly IHostEnvironment _environment;
    private readonly IAuthStore _authStore;
    private readonly IPasswordHasher _passwordHasher;
    private readonly IClock _clock;
    private readonly AuthOptions _options;
    private readonly ILogger<DevelopmentAdminBootstrapHostedService> _logger;

    public DevelopmentAdminBootstrapHostedService(
        IHostEnvironment environment,
        IAuthStore authStore,
        IPasswordHasher passwordHasher,
        IClock clock,
        IOptions<AuthOptions> options,
        ILogger<DevelopmentAdminBootstrapHostedService> logger)
    {
        _environment = environment;
        _authStore = authStore;
        _passwordHasher = passwordHasher;
        _clock = clock;
        _options = options.Value;
        _logger = logger;
    }

    public async Task StartAsync(CancellationToken cancellationToken)
    {
        if (!_environment.IsDevelopment() ||
            string.IsNullOrWhiteSpace(_options.ConnectionString) ||
            string.IsNullOrWhiteSpace(_options.BootstrapAdminEmail) ||
            string.IsNullOrWhiteSpace(_options.BootstrapAdminPassword))
        {
            return;
        }

        await _authStore.EnsureDevelopmentAdminAsync(
            _options.BootstrapAdminEmail,
            _passwordHasher.HashPassword(_options.BootstrapAdminPassword),
            _clock.UtcNow,
            cancellationToken);

        _logger.LogWarning("Development bootstrap admin ensured for {Email}.", _options.BootstrapAdminEmail);
    }

    public Task StopAsync(CancellationToken cancellationToken) => Task.CompletedTask;
}
