namespace ToxicAnalyzer.Domain.Analysis;

public sealed record AnalysisBatchSummary(
    int Total,
    int ToxicCount,
    int NonToxicCount,
    decimal AverageToxicProbability);
