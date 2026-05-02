namespace ToxicAnalyzer.Application.Auth;

public sealed class AuthOptions
{
    public const string SectionName = "Auth";

    public bool Enabled { get; set; } = true;

    public string Issuer { get; set; } = "toxic-analyzer";

    public string Audience { get; set; } = "toxic-analyzer-api";

    public string SigningKey { get; set; } = "change-this-development-signing-key-with-at-least-32-bytes";

    public string AnonymousCookieName { get; set; } = "ta_actor";

    public string SessionCookieName { get; set; } = "ta_session";

    public string CsrfCookieName { get; set; } = "ta_csrf";

    public string? ConnectionString { get; set; }

    public string Schema { get; set; } = "public";

    public string AdminRole { get; set; } = "admin";

    public string TrustedServiceRole { get; set; } = "trusted_service";

    public TimeSpan BrowserSessionLifetime { get; set; } = TimeSpan.FromDays(7);

    public TimeSpan ServiceAccessTokenLifetime { get; set; } = TimeSpan.FromMinutes(15);

    public string? BootstrapAdminEmail { get; set; }

    public string? BootstrapAdminPassword { get; set; }
}
