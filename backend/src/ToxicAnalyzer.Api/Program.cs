using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using ToxicAnalyzer.Api.Common.DependencyInjection;
using ToxicAnalyzer.Api.Common.ErrorHandling;
using ToxicAnalyzer.Api.Endpoints;
using ToxicAnalyzer.Infrastructure;
using ToxicAnalyzer.Infrastructure.ModelService;

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
    .AddCheck<ModelServiceHealthCheck>("ready", tags: ["ready"]);

var app = builder.Build();

app.UseExceptionHandler();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
    app.UseSwaggerUI(options =>
    {
        options.SwaggerEndpoint("/openapi/v1.json", "Toxic Analyzer API v1");
        options.RoutePrefix = "swagger";
    });
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
