using System.Collections.Concurrent;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class InMemoryAuthenticationAttemptLimiter : IAuthenticationAttemptLimiter
{
    private readonly ConcurrentDictionary<string, AttemptState> _loginAttempts = new(StringComparer.OrdinalIgnoreCase);
    private readonly ConcurrentDictionary<string, AttemptState> _serviceTokenAttempts = new(StringComparer.OrdinalIgnoreCase);
    private readonly IClock _clock;
    private readonly AuthOptions _options;

    public InMemoryAuthenticationAttemptLimiter(
        IClock clock,
        IOptions<AuthOptions> options)
    {
        _clock = clock;
        _options = options.Value;
    }

    public void ThrowIfLoginBlocked(string email)
    {
        ThrowIfBlocked(_loginAttempts, NormalizeKey(email), _options.LoginLockoutDuration);
    }

    public void RecordLoginFailure(string email)
    {
        RecordFailure(
            _loginAttempts,
            NormalizeKey(email),
            _options.LoginFailureWindow,
            _options.LoginMaxFailedAttempts,
            _options.LoginLockoutDuration);
    }

    public void ResetLoginFailures(string email)
    {
        _loginAttempts.TryRemove(NormalizeKey(email), out _);
    }

    public void ThrowIfServiceTokenBlocked(string clientId)
    {
        ThrowIfBlocked(_serviceTokenAttempts, NormalizeKey(clientId), _options.ServiceTokenLockoutDuration);
    }

    public void RecordServiceTokenFailure(string clientId)
    {
        RecordFailure(
            _serviceTokenAttempts,
            NormalizeKey(clientId),
            _options.ServiceTokenFailureWindow,
            _options.ServiceTokenMaxFailedAttempts,
            _options.ServiceTokenLockoutDuration);
    }

    public void ResetServiceTokenFailures(string clientId)
    {
        _serviceTokenAttempts.TryRemove(NormalizeKey(clientId), out _);
    }

    private void ThrowIfBlocked(
        ConcurrentDictionary<string, AttemptState> attempts,
        string key,
        TimeSpan defaultLockout)
    {
        if (!attempts.TryGetValue(key, out var state))
        {
            return;
        }

        var now = _clock.UtcNow;
        if (state.BlockedUntil is null || state.BlockedUntil <= now)
        {
            if (state.FirstFailedAt + defaultLockout <= now)
            {
                attempts.TryRemove(key, out _);
            }

            return;
        }

        throw new RateLimitExceededException(
            "Too many failed authentication attempts. Try again later.",
            state.BlockedUntil.Value - now);
    }

    private void RecordFailure(
        ConcurrentDictionary<string, AttemptState> attempts,
        string key,
        TimeSpan failureWindow,
        int maxFailedAttempts,
        TimeSpan lockoutDuration)
    {
        var now = _clock.UtcNow;
        attempts.AddOrUpdate(
            key,
            _ => CreateInitialState(now),
            (_, existing) =>
            {
                if (existing.BlockedUntil is not null && existing.BlockedUntil > now)
                {
                    return existing;
                }

                if (existing.FirstFailedAt + failureWindow <= now)
                {
                    return CreateInitialState(now);
                }

                var nextCount = existing.FailureCount + 1;
                return existing with
                {
                    FailureCount = nextCount,
                    BlockedUntil = nextCount >= maxFailedAttempts ? now.Add(lockoutDuration) : null
                };
            });
    }

    private static AttemptState CreateInitialState(DateTimeOffset now)
    {
        return new AttemptState(now, 1, null);
    }

    private static string NormalizeKey(string value)
    {
        return value.Trim();
    }

    private sealed record AttemptState(
        DateTimeOffset FirstFailedAt,
        int FailureCount,
        DateTimeOffset? BlockedUntil);
}
