namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeBatchItemRequest(string? ClientItemId, string Text);
