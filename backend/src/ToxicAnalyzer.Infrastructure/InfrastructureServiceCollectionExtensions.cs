using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
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
        IConfiguration configuration,
        IHostEnvironment environment)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);
        ArgumentNullException.ThrowIfNull(environment);

        services
            .AddOptions<ModelServiceOptions>()
            .Bind(configuration.GetSection(ModelServiceOptions.SectionName))
            .ValidateOnStart();
        services.AddSingleton<IValidateOptions<ModelServiceOptions>>(new ModelServiceOptionsValidator(environment));
        services.AddSingleton<ModelServiceConcurrencyGate>();
        services.AddTransient<ModelServiceAuthenticationHandler>();
        services.AddTransient<ModelServiceConcurrencyHandler>();

        services.AddHttpClient<IModelPredictionClient, ModelServiceClient>((serviceProvider, httpClient) =>
        {
            ConfigureHttpClient(serviceProvider, httpClient);
        })
            .AddHttpMessageHandler<ModelServiceAuthenticationHandler>()
            .AddHttpMessageHandler<ModelServiceConcurrencyHandler>();

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
        services.AddSingleton<AnalysisCaptureDbConnectionFactory>();
        services.AddSingleton<AnalysisCaptureSchemaInitializer>();
        services.AddSingleton<IAnalysisTextStore, PostgresAnalysisCaptureStore>();
        services.AddSingleton<IAnalysisTextVotingRepository, PostgresAnalysisTextVotingRepository>();
        services.AddHostedService<AnalysisCaptureBackgroundService>();

        return services;
    }

    public static IServiceCollection AddAuthInfrastructure(
        this IServiceCollection services,
        IConfiguration configuration,
        IHostEnvironment environment)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);
        ArgumentNullException.ThrowIfNull(environment);

        services
            .AddOptions<AuthOptions>()
            .Bind(configuration.GetSection(AuthOptions.SectionName))
            .ValidateOnStart();
        services.AddSingleton<IValidateOptions<AuthOptions>>(new AuthOptionsValidator(environment));

        services.AddSingleton(serviceProvider => serviceProvider.GetRequiredService<IOptions<AuthOptions>>().Value);
        services.AddSingleton<IPasswordHasher, PasswordHasher>();
        services.AddSingleton<ISessionTokenService, SessionTokenService>();
        services.AddSingleton<IAccessTokenIssuer, JwtAccessTokenIssuer>();
        services.AddSingleton<IAuthenticationAttemptLimiter, InMemoryAuthenticationAttemptLimiter>();
        services.AddSingleton<AuthDbConnectionFactory>();
        services.AddSingleton<AuthSchemaInitializer>();
        services.AddSingleton<IAuthStore, PostgresAuthStore>();
        services.AddHostedService<DevelopmentAdminBootstrapHostedService>();

        return services;
    }

    private static string EnsureTrailingSlash(string value)
    {
        return value.EndsWith("/", StringComparison.Ordinal) ? value : $"{value}/";
    }
}
