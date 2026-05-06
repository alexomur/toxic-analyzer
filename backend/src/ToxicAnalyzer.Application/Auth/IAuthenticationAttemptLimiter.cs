namespace ToxicAnalyzer.Application.Auth;

public interface IAuthenticationAttemptLimiter
{
    void ThrowIfLoginBlocked(string email);

    void RecordLoginFailure(string email);

    void ResetLoginFailures(string email);

    void ThrowIfServiceTokenBlocked(string clientId);

    void RecordServiceTokenFailure(string clientId);

    void ResetServiceTokenFailures(string clientId);
}
