namespace ToxicAnalyzer.Application.Auth;

public interface IAccessTokenIssuer
{
    ServiceAccessTokenResult IssueServiceAccessToken(
        AuthServiceClient client,
        IReadOnlyList<string> capabilities,
        DateTimeOffset issuedAt,
        DateTimeOffset expiresAt);
}
