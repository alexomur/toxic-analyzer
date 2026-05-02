using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.Hosting;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.DependencyInjection.Extensions;
using Microsoft.IdentityModel.Tokens;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class ApiWebApplicationFactory : WebApplicationFactory<Program>
{
    public const string TestIssuer = "toxicity-tests";
    public const string TestAudience = "toxicity-tests-api";
    public const string TestSigningKey = "toxicity-tests-signing-key-with-at-least-32-bytes";

    private readonly FakeModelPredictionClient _modelPredictionClient = new();
    private readonly FakeAnalysisCaptureScheduler _analysisCaptureScheduler = new();
    private readonly FakeAnalysisTextVotingRepository _analysisTextVotingRepository = new();
    private readonly FakeAuthStore _authStore = new();
    private readonly FakeClock _clock = new(DateTimeOffset.UtcNow);

    public FakeModelPredictionClient ModelPredictionClient => _modelPredictionClient;

    public FakeAnalysisCaptureScheduler AnalysisCaptureScheduler => _analysisCaptureScheduler;

    public FakeAnalysisTextVotingRepository AnalysisTextVotingRepository => _analysisTextVotingRepository;

    public FakeAuthStore AuthStore => _authStore;

    public FakeClock Clock => _clock;

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Development");
        builder.ConfigureAppConfiguration((_, configurationBuilder) =>
        {
            configurationBuilder.AddInMemoryCollection(new Dictionary<string, string?>
            {
                [$"{AuthOptions.SectionName}:Issuer"] = TestIssuer,
                [$"{AuthOptions.SectionName}:Audience"] = TestAudience,
                [$"{AuthOptions.SectionName}:SigningKey"] = TestSigningKey,
                [$"{AuthOptions.SectionName}:AnonymousCookieName"] = "ta_test_actor"
            });
        });

        builder.ConfigureServices(services =>
        {
            services.RemoveAll<IModelPredictionClient>();
            services.RemoveAll<IAnalysisCaptureScheduler>();
            services.RemoveAll<IAnalysisTextVotingRepository>();
            services.RemoveAll<IClock>();
            services.RemoveAll<IAuthStore>();

            services.AddSingleton<IModelPredictionClient>(_modelPredictionClient);
            services.AddSingleton<IAnalysisCaptureScheduler>(_analysisCaptureScheduler);
            services.AddSingleton<IAnalysisTextVotingRepository>(_analysisTextVotingRepository);
            services.AddSingleton<IClock>(_clock);
            services.AddSingleton<IAuthStore>(_authStore);
        });
    }

    public static string CreateAccessToken(
        string subjectId,
        string actorType = "user",
        IEnumerable<string>? roles = null,
        IEnumerable<string>? capabilities = null,
        string? clientId = null,
        string? tenantId = null)
    {
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, subjectId),
            new(ClaimTypes.NameIdentifier, subjectId),
            new(AuthClaimTypes.ActorType, actorType),
            new(AuthClaimTypes.AuthScheme, "Bearer")
        };

        if (!string.IsNullOrWhiteSpace(clientId))
        {
            claims.Add(new Claim(AuthClaimTypes.ClientId, clientId));
        }

        if (!string.IsNullOrWhiteSpace(tenantId))
        {
            claims.Add(new Claim(AuthClaimTypes.TenantId, tenantId));
        }

        if (roles is not null)
        {
            claims.AddRange(roles.Select(role => new Claim(ClaimTypes.Role, role)));
        }

        if (capabilities is not null)
        {
            var resolvedCapabilities = capabilities.Distinct(StringComparer.Ordinal).ToArray();
            claims.AddRange(resolvedCapabilities.Select(capability => new Claim(AuthClaimTypes.Capability, capability)));
            claims.Add(new Claim(AuthClaimTypes.Scope, string.Join(' ', resolvedCapabilities)));
        }

        var credentials = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(TestSigningKey)),
            SecurityAlgorithms.HmacSha256);

        var token = new JwtSecurityToken(
            issuer: TestIssuer,
            audience: TestAudience,
            claims: claims,
            notBefore: DateTime.UtcNow.AddMinutes(-1),
            expires: DateTime.UtcNow.AddHours(1),
            signingCredentials: credentials);

        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
