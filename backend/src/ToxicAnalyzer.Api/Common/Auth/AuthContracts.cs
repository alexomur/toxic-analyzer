namespace ToxicAnalyzer.Api.Common.Auth;

public sealed record RegisterRequest(string Email, string Password, string? Username);

public sealed record LoginRequest(string Email, string Password);

public sealed record ServiceTokenRequest(string ClientId, string ClientSecret);

public sealed record AuthSessionResponse(
    string ActorType,
    string Email,
    string? Username,
    string CsrfToken,
    DateTimeOffset ExpiresAt,
    string[] Capabilities);

public sealed record AuthActorResponse(
    string ActorType,
    string SubjectId,
    string? ClientId,
    string? TenantId,
    string? SessionId,
    string AuthScheme,
    string? Email,
    string? Name,
    string? CsrfToken,
    string[] Roles,
    string[] Capabilities,
    string[] Scopes);

public sealed record ServiceTokenResponse(
    string TokenType,
    string AccessToken,
    DateTimeOffset ExpiresAt,
    string SubjectId,
    string ClientId,
    bool IsTrusted,
    string[] Capabilities);
