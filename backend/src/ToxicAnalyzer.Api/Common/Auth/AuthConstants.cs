namespace ToxicAnalyzer.Api.Common.Auth;

public static class AuthConstants
{
    public const string SessionScheme = "Session";
    public const string BearerScheme = "Bearer";
    public const string CombinedScheme = "Combined";
    public const string SessionIdClaimType = "sid";
    public const string CsrfHeaderName = "X-CSRF-Token";
}
