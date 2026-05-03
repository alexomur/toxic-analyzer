namespace ToxicAnalyzer.Api.Common.Frontend;

public sealed class FrontendOptions
{
    public const string SectionName = "Frontend";

    public string[] AllowedOrigins { get; init; } = [];

    public bool HasAllowedOrigins => AllowedOrigins.Length > 0;
}
