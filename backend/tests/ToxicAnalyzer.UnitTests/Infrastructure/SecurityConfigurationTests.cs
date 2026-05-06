using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging.Abstractions;
using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Infrastructure.Auth;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class SecurityConfigurationTests
{
    [Theory]
    [InlineData("public")]
    [InlineData("_auth")]
    [InlineData("auth_v2")]
    public void AuthSchemaValidator_AcceptsSafeIdentifiers(string schema)
    {
        var validator = new AuthOptionsValidator(new FakeHostEnvironment("Production"));
        var options = CreateAuthOptions();
        options.Schema = schema;
        var result = validator.Validate(
            null,
            options);

        Assert.True(result.Succeeded);
    }

    [Theory]
    [InlineData("")]
    [InlineData("public;drop schema public;")]
    [InlineData("public schema")]
    public void AuthSchemaValidator_RejectsUnsafeIdentifiers(string schema)
    {
        var validator = new AuthOptionsValidator(new FakeHostEnvironment("Production"));
        var options = CreateAuthOptions();
        options.Schema = schema;
        var result = validator.Validate(
            null,
            options);

        Assert.False(result.Succeeded);
        Assert.Contains(result.Failures!, failure => failure.Contains("Schema"));
    }

    [Fact]
    public void ProductionAuthValidator_RejectsDevelopmentSecrets()
    {
        var validator = new AuthOptionsValidator(new FakeHostEnvironment("Production"));
        var options = CreateAuthOptions();
        options.SigningKey = AuthOptionsValidator.DevelopmentSigningKey;
        options.BootstrapAdminEmail = AuthOptionsValidator.DevelopmentBootstrapAdminEmail;
        options.BootstrapAdminPassword = AuthOptionsValidator.DevelopmentBootstrapAdminPassword;
        var result = validator.Validate(
            null,
            options);

        Assert.False(result.Succeeded);
        Assert.Contains(result.Failures!, failure => failure.Contains("SigningKey"));
        Assert.Contains(result.Failures!, failure => failure.Contains("Bootstrap admin"));
    }

    [Fact]
    public void ProductionModelServiceValidator_RejectsDefaultInternalApiKey()
    {
        var validator = new ModelServiceOptionsValidator(new FakeHostEnvironment("Production"));
        var result = validator.Validate(
            null,
            new ModelServiceOptions
            {
                BaseUrl = "http://model.internal/",
                Timeout = TimeSpan.FromSeconds(5),
                InternalApiKeyHeaderName = "X-Internal-Api-Key",
                InternalApiKey = ModelServiceOptionsValidator.DevelopmentInternalApiKey,
                MaxConcurrentRequests = 4
            });

        Assert.False(result.Succeeded);
        Assert.Contains(result.Failures!, failure => failure.Contains("InternalApiKey"));
    }

    [Fact]
    public async Task AuthSchemaInitializer_RejectsUnsafeSchemaAtRuntime()
    {
        var initializer = new AuthSchemaInitializer(
            Options.Create(new AuthOptions
            {
                Issuer = "issuer",
                Audience = "audience",
                SigningKey = "01234567890123456789012345678901",
                Schema = "public;drop schema public;"
            }),
            NullLogger<AuthSchemaInitializer>.Instance);

        await Assert.ThrowsAsync<InvalidOperationException>(() =>
            initializer.EnsureReadyAsync(new NpgsqlConnection(), CancellationToken.None));
    }

    private static AuthOptions CreateAuthOptions()
    {
        return new AuthOptions
        {
            Issuer = "issuer",
            Audience = "audience",
            SigningKey = "01234567890123456789012345678901",
            Schema = "public",
            BrowserSessionLifetime = TimeSpan.FromDays(1),
            ServiceAccessTokenLifetime = TimeSpan.FromMinutes(15),
            LoginFailureWindow = TimeSpan.FromMinutes(15),
            LoginLockoutDuration = TimeSpan.FromMinutes(10),
            ServiceTokenFailureWindow = TimeSpan.FromMinutes(15),
            ServiceTokenLockoutDuration = TimeSpan.FromMinutes(10),
            LoginMaxFailedAttempts = 5,
            ServiceTokenMaxFailedAttempts = 5
        };
    }

    private sealed class FakeHostEnvironment : IHostEnvironment
    {
        public FakeHostEnvironment(string environmentName)
        {
            EnvironmentName = environmentName;
        }

        public string EnvironmentName { get; set; }

        public string ApplicationName { get; set; } = "tests";

        public string ContentRootPath { get; set; } = AppContext.BaseDirectory;

        public Microsoft.Extensions.FileProviders.IFileProvider ContentRootFileProvider { get; set; } =
            new Microsoft.Extensions.FileProviders.NullFileProvider();
    }
}
