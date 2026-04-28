namespace ToxicAnalyzer.Application.Toxicity.AnalyzeText;

public sealed record AnalyzeTextResult(
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelDescriptor Model,
    DateTimeOffset CreatedAt);
