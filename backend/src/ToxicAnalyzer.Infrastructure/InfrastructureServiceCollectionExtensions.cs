using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.Infrastructure;

public static class InfrastructureServiceCollectionExtensions
{
    public static IServiceCollection AddModelServiceInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<ModelServiceOptions>()
            .Bind(configuration.GetSection(ModelServiceOptions.SectionName))
            .Validate(
                options => Uri.TryCreate(options.BaseUrl, UriKind.Absolute, out _),
                $"{ModelServiceOptions.SectionName}:BaseUrl must be an absolute URL.")
            .Validate(
                options => options.Timeout > TimeSpan.Zero,
                $"{ModelServiceOptions.SectionName}:Timeout must be greater than zero.")
            .ValidateOnStart();

        services.AddHttpClient<IModelPredictionClient, ModelServiceClient>((serviceProvider, httpClient) =>
        {
            var options = serviceProvider.GetRequiredService<IOptions<ModelServiceOptions>>().Value;
            httpClient.BaseAddress = new Uri(EnsureTrailingSlash(options.BaseUrl), UriKind.Absolute);
            httpClient.Timeout = options.Timeout;
        });

        return services;
    }

    private static string EnsureTrailingSlash(string value)
    {
        return value.EndsWith("/", StringComparison.Ordinal) ? value : $"{value}/";
    }
}
