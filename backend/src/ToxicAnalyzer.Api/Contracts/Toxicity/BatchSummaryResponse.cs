namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record BatchSummaryResponse(
    int Total,
    int ToxicCount,
    int NonToxicCount,
    decimal AverageToxicProbability);
