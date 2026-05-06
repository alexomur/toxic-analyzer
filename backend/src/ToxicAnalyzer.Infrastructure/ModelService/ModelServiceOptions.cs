namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceOptions
{
    public const string SectionName = "ModelService";

    public string BaseUrl { get; set; } = string.Empty;

    public TimeSpan Timeout { get; set; } = TimeSpan.FromSeconds(10);

    public string InternalApiKeyHeaderName { get; set; } = "X-Internal-Api-Key";

    public string? InternalApiKey { get; set; }

    public int MaxConcurrentRequests { get; set; } = 16;
}
