using ToxicAnalyzer.Domain.Common;

namespace ToxicAnalyzer.Domain.Analysis;

public sealed record ModelIdentity
{
    private ModelIdentity(string modelKey, string modelVersion)
    {
        ModelKey = modelKey;
        ModelVersion = modelVersion;
    }

    public string ModelKey { get; }

    public string ModelVersion { get; }

    public static ModelIdentity Create(string modelKey, string modelVersion)
    {
        return new ModelIdentity(
            Guard.AgainstNullOrWhiteSpace(modelKey, nameof(modelKey)).Trim(),
            Guard.AgainstNullOrWhiteSpace(modelVersion, nameof(modelVersion)).Trim());
    }
}
