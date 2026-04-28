namespace ToxicAnalyzer.Application.Toxicity;

public sealed record BatchSummaryModel(
    int Total,
    int ToxicCount,
    int NonToxicCount,
    decimal AverageToxicProbability);
