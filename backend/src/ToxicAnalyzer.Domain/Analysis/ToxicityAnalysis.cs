using ToxicAnalyzer.Domain.Common;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Domain.Analysis;

public sealed class ToxicityAnalysis : Entity<AnalysisId>
{
    private ToxicityAnalysis(
        AnalysisId id,
        TextContent text,
        TextFingerprint textFingerprint,
        PredictionLabel label,
        ToxicProbability toxicProbability,
        ModelIdentity model,
        DateTimeOffset createdAt) : base(id)
    {
        Text = text;
        TextFingerprint = textFingerprint;
        Label = label;
        ToxicProbability = toxicProbability;
        Model = model;
        CreatedAt = createdAt;
    }

    public TextContent Text { get; }

    public TextFingerprint TextFingerprint { get; }

    public PredictionLabel Label { get; }

    public ToxicProbability ToxicProbability { get; }

    public ModelIdentity Model { get; }

    public DateTimeOffset CreatedAt { get; }

    public static ToxicityAnalysis Create(
        TextContent text,
        PredictionLabel label,
        ToxicProbability toxicProbability,
        ModelIdentity model,
        DateTimeOffset createdAt,
        AnalysisId? id = null)
    {
        ArgumentNullException.ThrowIfNull(text);
        ArgumentNullException.ThrowIfNull(model);
        Guard.AgainstDefault(createdAt, nameof(createdAt));

        return new ToxicityAnalysis(
            id ?? AnalysisId.New(),
            text,
            TextFingerprint.From(text),
            label,
            toxicProbability,
            model,
            createdAt);
    }
}
