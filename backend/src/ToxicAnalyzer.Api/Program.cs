using Microsoft.AspNetCore.Diagnostics.HealthChecks;
using ToxicAnalyzer.Api.Common.Auth;
using ToxicAnalyzer.Api.Common.DependencyInjection;
using ToxicAnalyzer.Api.Common.ErrorHandling;
using ToxicAnalyzer.Api.Common.Frontend;
using ToxicAnalyzer.Api.Common.Security;
using ToxicAnalyzer.Api.Endpoints;
using ToxicAnalyzer.Infrastructure;
using ToxicAnalyzer.Infrastructure.ModelService;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<GlobalExceptionHandler>();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddAuthInfrastructure(builder.Configuration, builder.Environment);
builder.Services.AddApiServices(builder.Configuration);
builder.Services.AddModelServiceInfrastructure(builder.Configuration, builder.Environment);
builder.Services.AddAnalysisCaptureInfrastructure(builder.Configuration);
builder.Services
    .AddHealthChecks()
    .AddCheck("live", () => Microsoft.Extensions.Diagnostics.HealthChecks.HealthCheckResult.Healthy(), tags: ["live"])
    .AddCheck<ModelServiceHealthCheck>("ready", tags: ["ready"]);

var app = builder.Build();

app.UseExceptionHandler();
app.UseForwardedHeaders();
if (!app.Environment.IsDevelopment())
{
    app.UseHsts();
    app.UseHttpsRedirection();
}

app.UseMiddleware<RequestBodySizeLimitMiddleware>();
var frontendOptions = app.Services.GetRequiredService<FrontendOptions>();
if (frontendOptions.HasAllowedOrigins)
{
    app.UseCors("Frontend");
}
app.UseAuthentication();
app.UseRateLimiter();
app.UseAuthorization();
app.UseMiddleware<CsrfProtectionMiddleware>();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger(options =>
    {
        options.RouteTemplate = "openapi/{documentName}.json";
    });
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
app.MapAuthEndpoints();

app.Run();

public partial class Program;
