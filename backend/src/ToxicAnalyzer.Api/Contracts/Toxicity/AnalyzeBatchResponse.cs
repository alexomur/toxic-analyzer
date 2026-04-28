namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeBatchResponse(
    string BatchId,
    IReadOnlyList<AnalyzeBatchItemResponse> Items,
    BatchSummaryResponse Summary,
    DateTimeOffset CreatedAt);
