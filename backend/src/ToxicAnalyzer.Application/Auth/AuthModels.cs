namespace ToxicAnalyzer.Application.Auth;

public sealed record AuthUser(
    Guid Id,
    string Email,
    string? Username,
    string Role,
    string PasswordHash,
    string Status,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt);

public sealed record SessionIssueResult(
    string SessionId,
    string SessionToken,
    string CsrfToken,
    DateTimeOffset ExpiresAt);

public sealed record AuthenticatedSession(
    string SessionId,
    AuthUser User,
    DateTimeOffset ExpiresAt,
    DateTimeOffset LastSeenAt,
    IReadOnlyList<string> Capabilities);

public sealed record AuthServiceClient(
    Guid Id,
    string ClientId,
    string DisplayName,
    bool IsTrusted,
    string Status,
    string? TenantId,
    DateTimeOffset CreatedAt,
    DateTimeOffset UpdatedAt);

public sealed record AuthClientSecret(
    Guid Id,
    string SecretHash,
    DateTimeOffset CreatedAt,
    DateTimeOffset? ExpiresAt,
    DateTimeOffset? RevokedAt);

public sealed record ServiceClientAuthenticationInfo(
    AuthServiceClient Client,
    IReadOnlyList<AuthClientSecret> Secrets,
    IReadOnlyList<string> Capabilities);

public sealed record BrowserSessionResult(
    AuthUser User,
    SessionIssueResult Session,
    IReadOnlyList<string> Capabilities);

public sealed record ServiceAccessTokenResult(
    string AccessToken,
    string TokenType,
    DateTimeOffset ExpiresAt,
    string SubjectId,
    string ClientId,
    bool IsTrusted,
    IReadOnlyList<string> Capabilities);
