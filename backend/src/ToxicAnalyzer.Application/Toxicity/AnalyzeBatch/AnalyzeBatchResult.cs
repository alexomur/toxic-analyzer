namespace ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;

public sealed record AnalyzeBatchResult(
    string BatchId,
    IReadOnlyList<AnalyzeBatchResultItem> Items,
    BatchSummaryModel Summary,
    DateTimeOffset CreatedAt);
