using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;
using ToxicAnalyzer.Application.Toxicity.GetTextById;
using ToxicAnalyzer.Application.Toxicity.VoteText;

namespace ToxicAnalyzer.Api.Common.DependencyInjection;

public static class ApiServiceCollectionExtensions
{
    public static IServiceCollection AddApiServices(this IServiceCollection services)
    {
        ArgumentNullException.ThrowIfNull(services);

        services.AddSingleton<IClock, SystemClock>();
        services.AddSingleton<IAnalysisCaptureScheduler, NoOpAnalysisCaptureScheduler>();
        services.AddScoped<AnalyzeTextHandler>();
        services.AddScoped<AnalyzeBatchHandler>();
        services.AddScoped<GetRandomTextHandler>();
        services.AddScoped<GetTextByIdHandler>();
        services.AddScoped<VoteTextHandler>();

        return services;
    }

    private sealed class SystemClock : IClock
    {
        public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
    }
}
