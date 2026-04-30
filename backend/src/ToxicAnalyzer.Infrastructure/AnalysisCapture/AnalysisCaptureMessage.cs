using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed record AnalysisCaptureMessage(
    string TextFingerprint,
    string NormalizedText,
    DateTimeOffset CapturedAt,
    PredictionLabel Label,
    ToxicProbability ToxicProbability,
    ModelIdentity Model,
    string SourceKind,
    string? ActorId,
    string? TenantId)
{
    public static AnalysisCaptureMessage FromAnalysis(
        ToxicityAnalysis analysis,
        string sourceKind,
        string? actorId = null,
        string? tenantId = null)
    {
        ArgumentNullException.ThrowIfNull(analysis);

        return new AnalysisCaptureMessage(
            analysis.TextFingerprint.Value,
            analysis.Text.Normalized,
            analysis.CreatedAt,
            analysis.Label,
            analysis.ToxicProbability,
            analysis.Model,
            sourceKind,
            actorId,
            tenantId);
    }
}
