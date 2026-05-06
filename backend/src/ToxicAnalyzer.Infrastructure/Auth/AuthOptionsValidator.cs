using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class AuthOptionsValidator : IValidateOptions<AuthOptions>
{
    public const string DevelopmentSigningKey = "development-signing-key-change-before-production-12345";
    public const string DevelopmentBootstrapAdminEmail = "admin@local.test";
    public const string DevelopmentBootstrapAdminPassword = "Admin12345!";

    private readonly IHostEnvironment _environment;

    public AuthOptionsValidator(IHostEnvironment environment)
    {
        _environment = environment;
    }

    public ValidateOptionsResult Validate(string? name, AuthOptions options)
    {
        var errors = new List<string>();

        if (string.IsNullOrWhiteSpace(options.Issuer))
        {
            errors.Add($"{AuthOptions.SectionName}:Issuer is required.");
        }

        if (string.IsNullOrWhiteSpace(options.Audience))
        {
            errors.Add($"{AuthOptions.SectionName}:Audience is required.");
        }

        if (string.IsNullOrWhiteSpace(options.SigningKey) || options.SigningKey.Length < 32)
        {
            errors.Add($"{AuthOptions.SectionName}:SigningKey must be at least 32 characters.");
        }

        if (options.BrowserSessionLifetime <= TimeSpan.Zero)
        {
            errors.Add($"{AuthOptions.SectionName}:BrowserSessionLifetime must be greater than zero.");
        }

        if (options.ServiceAccessTokenLifetime <= TimeSpan.Zero)
        {
            errors.Add($"{AuthOptions.SectionName}:ServiceAccessTokenLifetime must be greater than zero.");
        }

        if (!AnalysisCapture.AnalysisCaptureOptions.IsValidSchema(options.Schema))
        {
            errors.Add($"{AuthOptions.SectionName}:Schema must be a valid PostgreSQL schema identifier.");
        }

        if (options.LoginMaxFailedAttempts <= 0)
        {
            errors.Add($"{AuthOptions.SectionName}:LoginMaxFailedAttempts must be greater than zero.");
        }

        if (options.LoginFailureWindow <= TimeSpan.Zero || options.LoginLockoutDuration <= TimeSpan.Zero)
        {
            errors.Add($"{AuthOptions.SectionName}:Login failure window and lockout duration must be greater than zero.");
        }

        if (options.ServiceTokenMaxFailedAttempts <= 0)
        {
            errors.Add($"{AuthOptions.SectionName}:ServiceTokenMaxFailedAttempts must be greater than zero.");
        }

        if (options.ServiceTokenFailureWindow <= TimeSpan.Zero || options.ServiceTokenLockoutDuration <= TimeSpan.Zero)
        {
            errors.Add($"{AuthOptions.SectionName}:Service token failure window and lockout duration must be greater than zero.");
        }

        if (!_environment.IsDevelopment())
        {
            if (string.Equals(options.SigningKey, DevelopmentSigningKey, StringComparison.Ordinal))
            {
                errors.Add($"{AuthOptions.SectionName}:SigningKey must be replaced outside Development.");
            }

            if (string.Equals(options.BootstrapAdminEmail, DevelopmentBootstrapAdminEmail, StringComparison.OrdinalIgnoreCase) &&
                string.Equals(options.BootstrapAdminPassword, DevelopmentBootstrapAdminPassword, StringComparison.Ordinal))
            {
                errors.Add($"{AuthOptions.SectionName}:Bootstrap admin default credentials are not allowed outside Development.");
            }
        }

        return errors.Count == 0 ? ValidateOptionsResult.Success : ValidateOptionsResult.Fail(errors);
    }
}
