namespace ToxicAnalyzer.Application.Abstractions;

public static class AnalysisTextOriginMappings
{
    public static string ToStorageValue(this AnalysisTextOrigin origin)
    {
        return origin switch
        {
            AnalysisTextOrigin.RandomPool => "random_pool",
            AnalysisTextOrigin.SelfSubmitted => "self_submitted",
            AnalysisTextOrigin.BotSubmitted => "bot_submitted",
            _ => throw new ArgumentOutOfRangeException(nameof(origin), origin, "Unsupported analysis text origin.")
        };
    }
}
