namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeBatchRequest(IReadOnlyList<AnalyzeBatchItemRequest> Items);
