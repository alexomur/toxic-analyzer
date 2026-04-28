namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceOptions
{
    public const string SectionName = "ModelService";

    public string BaseUrl { get; set; } = string.Empty;

    public TimeSpan Timeout { get; set; } = TimeSpan.FromSeconds(10);
}
