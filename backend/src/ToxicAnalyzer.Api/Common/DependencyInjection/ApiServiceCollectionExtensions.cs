using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Auth.IssueServiceToken;
using ToxicAnalyzer.Application.Auth.Login;
using ToxicAnalyzer.Application.Auth.Logout;
using ToxicAnalyzer.Application.Auth.Register;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;
using ToxicAnalyzer.Application.Toxicity.GetTextById;
using ToxicAnalyzer.Application.Toxicity.VoteText;
using ToxicAnalyzer.Api.Common.Auth;
using ToxicAnalyzer.Api.Common.OpenApi;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.OpenApi;
using Swashbuckle.AspNetCore.SwaggerGen;

namespace ToxicAnalyzer.Api.Common.DependencyInjection;

public static class ApiServiceCollectionExtensions
{
    public static IServiceCollection AddApiServices(this IServiceCollection services, IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(services);
        ArgumentNullException.ThrowIfNull(configuration);

        var authOptions = configuration.GetSection(AuthOptions.SectionName).Get<AuthOptions>() ?? new AuthOptions();

        services.AddHttpContextAccessor();
        services.AddDataProtection();
        services.AddSingleton<IAnonymousActorCookieService, AnonymousActorCookieService>();
        services.AddSingleton<ISessionCookieService, SessionCookieService>();
        services.AddScoped<ICurrentActorAccessor, HttpContextCurrentActorAccessor>();
        services
            .AddAuthentication(AuthConstants.CombinedScheme)
            .AddPolicyScheme(AuthConstants.CombinedScheme, AuthConstants.CombinedScheme, options =>
            {
                options.ForwardDefaultSelector = context =>
                {
                    return context.Request.Headers.ContainsKey("Authorization")
                        ? AuthConstants.BearerScheme
                        : AuthConstants.SessionScheme;
                };
            })
            .AddScheme<AuthenticationSchemeOptions, BearerTokenAuthenticationHandler>(
                AuthConstants.BearerScheme,
                options =>
            {
                options.ClaimsIssuer = authOptions.Issuer;
            })
            .AddScheme<AuthenticationSchemeOptions, SessionAuthenticationHandler>(
                AuthConstants.SessionScheme,
                options =>
            {
                options.ClaimsIssuer = authOptions.Issuer;
            });

        services.AddAuthorization(options =>
        {
            options.AddPolicy(AuthPolicies.RequireAuthenticated, policy => policy.RequireAuthenticatedUser());
            foreach (var capability in AuthCapabilities.All)
            {
                options.AddPolicy(AuthPolicies.Capability(capability), policy =>
                    policy.RequireAssertion(context =>
                        context.User.Identity?.IsAuthenticated == true &&
                        HasCapability(context.User, capability)));
            }
        });

        services.AddSwaggerGen(options =>
        {
            options.SwaggerDoc("v1", new OpenApiInfo
            {
                Title = "Toxic Analyzer API",
                Version = "v1",
                Description = "Development Swagger for Toxic Analyzer backend."
            });

            options.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
            {
                Type = SecuritySchemeType.Http,
                Scheme = "bearer",
                BearerFormat = "JWT",
                Description = "Paste a JWT access token for service or admin bearer auth."
            });

            options.AddSecurityDefinition("SessionCookie", new OpenApiSecurityScheme
            {
                Type = SecuritySchemeType.ApiKey,
                In = ParameterLocation.Cookie,
                Name = authOptions.SessionCookieName,
                Description = "Browser session cookie set by /api/v1/auth/register or /api/v1/auth/login."
            });

            options.AddSecurityDefinition("CsrfHeader", new OpenApiSecurityScheme
            {
                Type = SecuritySchemeType.ApiKey,
                In = ParameterLocation.Header,
                Name = AuthConstants.CsrfHeaderName,
                Description = "Use the csrfToken returned by auth endpoints for session-based write requests."
            });

            options.OperationFilter<SwaggerSecurityOperationFilter>();
        });

        services.AddSingleton<IClock, SystemClock>();
        services.AddSingleton<IAnalysisCaptureScheduler, NoOpAnalysisCaptureScheduler>();
        services.AddScoped<AnalyzeTextHandler>();
        services.AddScoped<AnalyzeBatchHandler>();
        services.AddScoped<GetRandomTextHandler>();
        services.AddScoped<GetTextByIdHandler>();
        services.AddScoped<VoteTextHandler>();
        services.AddScoped<RegisterUserHandler>();
        services.AddScoped<LoginUserHandler>();
        services.AddScoped<LogoutSessionHandler>();
        services.AddScoped<IssueServiceTokenHandler>();

        return services;
    }

    private static bool HasCapability(ClaimsPrincipal principal, string capability)
    {
        return principal.FindAll(AuthClaimTypes.Capability).Any(claim => string.Equals(claim.Value, capability, StringComparison.Ordinal)) ||
               principal.FindAll(AuthClaimTypes.Scope)
                   .SelectMany(claim => claim.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                   .Any(value => string.Equals(value, capability, StringComparison.Ordinal));
    }

    private sealed class SystemClock : IClock
    {
        public DateTimeOffset UtcNow => DateTimeOffset.UtcNow;
    }
}
