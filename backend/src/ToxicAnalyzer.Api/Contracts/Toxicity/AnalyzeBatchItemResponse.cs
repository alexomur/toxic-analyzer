namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeBatchItemResponse(
    string? ClientItemId,
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelInfoResponse Model);
