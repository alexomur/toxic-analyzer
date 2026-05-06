using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Auth.IssueServiceToken;

public sealed class IssueServiceTokenHandler
{
    private readonly IAuthStore _authStore;
    private readonly IPasswordHasher _passwordHasher;
    private readonly IAccessTokenIssuer _accessTokenIssuer;
    private readonly IClock _clock;
    private readonly AuthOptions _authOptions;
    private readonly IAuthenticationAttemptLimiter _attemptLimiter;

    public IssueServiceTokenHandler(
        IAuthStore authStore,
        IPasswordHasher passwordHasher,
        IAccessTokenIssuer accessTokenIssuer,
        IClock clock,
        AuthOptions authOptions,
        IAuthenticationAttemptLimiter attemptLimiter)
    {
        _authStore = authStore;
        _passwordHasher = passwordHasher;
        _accessTokenIssuer = accessTokenIssuer;
        _clock = clock;
        _authOptions = authOptions;
        _attemptLimiter = attemptLimiter;
    }

    public async Task<ServiceAccessTokenResult> HandleAsync(
        IssueServiceTokenCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        if (string.IsNullOrWhiteSpace(command.ClientId) || string.IsNullOrWhiteSpace(command.ClientSecret))
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("request", "clientId and clientSecret are required.")]);
        }

        var normalizedClientId = command.ClientId.Trim();
        _attemptLimiter.ThrowIfServiceTokenBlocked(normalizedClientId);

        var authenticationInfo = await _authStore.GetServiceClientAuthenticationInfoAsync(
            normalizedClientId,
            _clock.UtcNow,
            cancellationToken);

        if (authenticationInfo is null || !HasValidSecret(authenticationInfo, command.ClientSecret))
        {
            _attemptLimiter.RecordServiceTokenFailure(normalizedClientId);
            throw new AuthenticationFailedException("Invalid service client credentials.");
        }

        _attemptLimiter.ResetServiceTokenFailures(normalizedClientId);
        var expiresAt = _clock.UtcNow.Add(_authOptions.ServiceAccessTokenLifetime);
        return _accessTokenIssuer.IssueServiceAccessToken(
            authenticationInfo.Client,
            authenticationInfo.Capabilities,
            _clock.UtcNow,
            expiresAt);
    }

    private bool HasValidSecret(ServiceClientAuthenticationInfo authenticationInfo, string candidateSecret)
    {
        return authenticationInfo.Secrets.Any(secret =>
            secret.RevokedAt is null &&
            (secret.ExpiresAt is null || secret.ExpiresAt > _clock.UtcNow) &&
            _passwordHasher.VerifyPassword(candidateSecret, secret.SecretHash));
    }
}
