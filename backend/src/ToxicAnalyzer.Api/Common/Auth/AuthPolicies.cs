namespace ToxicAnalyzer.Api.Common.Auth;

public static class AuthPolicies
{
    public const string RequireAuthenticated = "RequireAuthenticated";

    public static string Capability(string capability) => $"capability:{capability}";
}
