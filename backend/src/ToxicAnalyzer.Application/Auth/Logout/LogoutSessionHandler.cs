using ToxicAnalyzer.Application.Abstractions;

namespace ToxicAnalyzer.Application.Auth.Logout;

public sealed class LogoutSessionHandler
{
    private readonly IAuthStore _authStore;
    private readonly IClock _clock;

    public LogoutSessionHandler(IAuthStore authStore, IClock clock)
    {
        _authStore = authStore;
        _clock = clock;
    }

    public Task HandleAsync(LogoutSessionCommand command, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        if (string.IsNullOrWhiteSpace(command.SessionId))
        {
            return Task.CompletedTask;
        }

        return _authStore.RevokeSessionAsync(command.SessionId, _clock.UtcNow, cancellationToken);
    }
}
