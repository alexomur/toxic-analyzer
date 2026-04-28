namespace ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;

public sealed record AnalyzeBatchResultItem(
    string? ClientItemId,
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelDescriptor Model);
