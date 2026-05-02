namespace ToxicAnalyzer.Application.Auth;

public interface IAuthStore
{
    Task<AuthUser?> GetUserByEmailAsync(string email, CancellationToken cancellationToken);

    Task<AuthUser?> GetUserByIdAsync(Guid userId, CancellationToken cancellationToken);

    Task<AuthUser> CreateUserAsync(
        string email,
        string? username,
        string passwordHash,
        string role,
        CancellationToken cancellationToken);

    Task<SessionIssueResult> CreateSessionAsync(
        Guid userId,
        string sessionTokenHash,
        string csrfTokenHash,
        DateTimeOffset createdAt,
        DateTimeOffset expiresAt,
        CancellationToken cancellationToken);

    Task<AuthenticatedSession?> GetAuthenticatedSessionAsync(
        string sessionTokenHash,
        DateTimeOffset now,
        CancellationToken cancellationToken);

    Task<bool> ValidateCsrfAsync(
        string sessionId,
        string csrfTokenHash,
        CancellationToken cancellationToken);

    Task RevokeSessionAsync(string sessionId, DateTimeOffset revokedAt, CancellationToken cancellationToken);

    Task EnsureDevelopmentAdminAsync(
        string email,
        string passwordHash,
        DateTimeOffset now,
        CancellationToken cancellationToken);

    Task<ServiceClientAuthenticationInfo?> GetServiceClientAuthenticationInfoAsync(
        string clientId,
        DateTimeOffset now,
        CancellationToken cancellationToken);
}
