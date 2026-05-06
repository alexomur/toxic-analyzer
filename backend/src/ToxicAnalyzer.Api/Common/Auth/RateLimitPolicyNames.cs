namespace ToxicAnalyzer.Api.Common.Auth;

public static class RateLimitPolicyNames
{
    public const string AuthCredential = "auth-credential";
    public const string ServiceToken = "service-token";
    public const string PublicAnalyze = "public-analyze";
    public const string ProtectedRead = "protected-read";
    public const string ProtectedVote = "protected-vote";
}
