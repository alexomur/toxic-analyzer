namespace ToxicAnalyzer.Application.Toxicity;

public sealed record AnalysisResultModel(
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelDescriptor Model,
    DateTimeOffset CreatedAt);
