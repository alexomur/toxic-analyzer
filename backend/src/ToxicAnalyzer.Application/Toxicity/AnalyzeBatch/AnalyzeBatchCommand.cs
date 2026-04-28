namespace ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;

public sealed record AnalyzeBatchCommand(IReadOnlyList<AnalyzeBatchItem> Items);
