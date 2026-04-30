using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using ToxicAnalyzer.Application.Abstractions;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class ApiWebApplicationFactory : WebApplicationFactory<Program>
{
    private readonly FakeModelPredictionClient _modelPredictionClient = new();
    private readonly FakeAnalysisCaptureScheduler _analysisCaptureScheduler = new();
    private readonly FakeClock _clock = new(new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero));

    public FakeModelPredictionClient ModelPredictionClient => _modelPredictionClient;

    public FakeAnalysisCaptureScheduler AnalysisCaptureScheduler => _analysisCaptureScheduler;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");

        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IModelPredictionClient>();
            services.RemoveAll<IAnalysisCaptureScheduler>();
            services.RemoveAll<IClock>();

            services.AddSingleton<IModelPredictionClient>(_modelPredictionClient);
            services.AddSingleton<IAnalysisCaptureScheduler>(_analysisCaptureScheduler);
            services.AddSingleton<IClock>(_clock);
        });
    }
}
