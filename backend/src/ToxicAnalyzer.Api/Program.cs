using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using ToxicAnalyzer.Api.Common.DependencyInjection;
using ToxicAnalyzer.Api.Common.ErrorHandling;
using ToxicAnalyzer.Api.Endpoints;
using ToxicAnalyzer.Infrastructure;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddOpenApi();
builder.Services.AddApiServices();
builder.Services.AddModelServiceInfrastructure(builder.Configuration);
builder.Services
    .AddHealthChecks()
    .AddCheck("live", () => Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy(), tags: ["live"])
    // TODO: add model service readiness probe when Infrastructure.ModelService exposes a dedicated health client.
    .AddCheck("ready", () => Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy(), tags: ["ready"]);

var app = builder.Build();

app.UseExceptionHandler();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.MapHealthChecks("/health/live", new HealthCheckOptions
{
    Predicate = registration => registration.Tags.Contains("live")
});

app.MapHealthChecks("/health/ready", new HealthCheckOptions
{
    Predicate = registration => registration.Tags.Contains("ready")
});

app.MapToxicityEndpoints();

app.Run();

public partial class Program;
