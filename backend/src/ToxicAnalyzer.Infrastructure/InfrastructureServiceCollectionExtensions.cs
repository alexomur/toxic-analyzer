using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Infrastructure.AnalysisCapture;
using ToxicAnalyzer.Infrastructure.Auth;
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
            ConfigureHttpClient(serviceProvider, httpClient);
        });

        services.AddHttpClient<ModelServiceHealthCheck>((serviceProvider, httpClient) =>
        {
            ConfigureHttpClient(serviceProvider, httpClient);
        });

        return services;
    }

    private static void ConfigureHttpClient(IServiceProvider serviceProvider, HttpClient httpClient)
    {
        var options = serviceProvider.GetRequiredService<IOptions<ModelServiceOptions>>().Value;
        httpClient.BaseAddress = new Uri(EnsureTrailingSlash(options.BaseUrl), UriKind.Absolute);
        httpClient.Timeout = options.Timeout;
    }

    public static IServiceCollection AddAnalysisCaptureInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<AnalysisCaptureOptions>()
            .Bind(configuration.GetSection(AnalysisCaptureOptions.SectionName))
            .Validate(
                options => !options.Enabled || !string.IsNullOrWhiteSpace(options.ConnectionString),
                $"{AnalysisCaptureOptions.SectionName}:ConnectionString is required when capture is enabled.")
            .Validate(
                options => !options.Enabled || AnalysisCaptureOptions.IsValidSchema(options.Schema),
                $"{AnalysisCaptureOptions.SectionName}:Schema must be a valid PostgreSQL schema identifier.")
            .Validate(
                options => options.QueueCapacity > 0,
                $"{AnalysisCaptureOptions.SectionName}:QueueCapacity must be greater than zero.")
            .Validate(
                options => options.BatchSize > 0,
                $"{AnalysisCaptureOptions.SectionName}:BatchSize must be greater than zero.")
            .Validate(
                options => options.FlushInterval > TimeSpan.Zero,
                $"{AnalysisCaptureOptions.SectionName}:FlushInterval must be greater than zero.")
            .ValidateOnStart();

        var options = configuration.GetSection(AnalysisCaptureOptions.SectionName).Get<AnalysisCaptureOptions>()
            ?? new AnalysisCaptureOptions();

        if (!options.Enabled)
        {
            services.AddSingleton<IAnalysisTextVotingRepository, DisabledAnalysisTextVotingRepository>();
            return services;
        }

        services.AddSingleton(new AnalysisCaptureQueue(options.QueueCapacity));
        services.AddSingleton<IAnalysisCaptureScheduler, AnalysisCaptureChannelScheduler>();
        services.AddSingleton<PostgresAnalysisTextStore>();
        services.AddSingleton<IAnalysisTextStore>(serviceProvider => serviceProvider.GetRequiredService<PostgresAnalysisTextStore>());
        services.AddSingleton<IAnalysisTextVotingRepository>(serviceProvider => serviceProvider.GetRequiredService<PostgresAnalysisTextStore>());
        services.AddHostedService<AnalysisCaptureBackgroundService>();

        return services;
    }

    public static IServiceCollection AddAuthInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        services
            .AddOptions<AuthOptions>()
            .Bind(configuration.GetSection(AuthOptions.SectionName))
            .Validate(options => !string.IsNullOrWhiteSpace(options.Issuer), $"{AuthOptions.SectionName}:Issuer is required.")
            .Validate(options => !string.IsNullOrWhiteSpace(options.Audience), $"{AuthOptions.SectionName}:Audience is required.")
            .Validate(options => !string.IsNullOrWhiteSpace(options.SigningKey) && options.SigningKey.Length >= 32, $"{AuthOptions.SectionName}:SigningKey must be at least 32 characters.")
            .Validate(options => options.BrowserSessionLifetime > TimeSpan.Zero, $"{AuthOptions.SectionName}:BrowserSessionLifetime must be greater than zero.")
            .Validate(options => options.ServiceAccessTokenLifetime > TimeSpan.Zero, $"{AuthOptions.SectionName}:ServiceAccessTokenLifetime must be greater than zero.")
            .ValidateOnStart();

        services.AddSingleton(serviceProvider => serviceProvider.GetRequiredService<IOptions<AuthOptions>>().Value);
        services.AddSingleton<IPasswordHasher, PasswordHasher>();
        services.AddSingleton<ISessionTokenService, SessionTokenService>();
        services.AddSingleton<IAccessTokenIssuer, JwtAccessTokenIssuer>();
        services.AddSingleton<IAuthStore, PostgresAuthStore>();
        services.AddHostedService<DevelopmentAdminBootstrapHostedService>();

        return services;
    }

    private static string EnsureTrailingSlash(string value)
    {
        return value.EndsWith("/", StringComparison.Ordinal) ? value : $"{value}/";
    }
}
