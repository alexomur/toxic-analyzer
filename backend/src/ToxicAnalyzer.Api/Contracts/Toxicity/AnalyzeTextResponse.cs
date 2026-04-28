namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeTextResponse(
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelInfoResponse Model,
    DateTimeOffset CreatedAt);
