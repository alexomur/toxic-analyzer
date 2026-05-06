using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Options;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceOptionsValidator : IValidateOptions<ModelServiceOptions>
{
    public const string DevelopmentInternalApiKey = "local-model-internal-key-change-me";

    private readonly IHostEnvironment _environment;

    public ModelServiceOptionsValidator(IHostEnvironment environment)
    {
        _environment = environment;
    }

    public ValidateOptionsResult Validate(string? name, ModelServiceOptions options)
    {
        var errors = new List<string>();

        if (!Uri.TryCreate(options.BaseUrl, UriKind.Absolute, out _))
        {
            errors.Add($"{ModelServiceOptions.SectionName}:BaseUrl must be an absolute URL.");
        }

        if (options.Timeout <= TimeSpan.Zero)
        {
            errors.Add($"{ModelServiceOptions.SectionName}:Timeout must be greater than zero.");
        }

        if (string.IsNullOrWhiteSpace(options.InternalApiKeyHeaderName))
        {
            errors.Add($"{ModelServiceOptions.SectionName}:InternalApiKeyHeaderName is required.");
        }

        if (options.MaxConcurrentRequests <= 0)
        {
            errors.Add($"{ModelServiceOptions.SectionName}:MaxConcurrentRequests must be greater than zero.");
        }

        if (!_environment.IsDevelopment())
        {
            if (string.IsNullOrWhiteSpace(options.InternalApiKey) ||
                options.InternalApiKey.Length < 32 ||
                string.Equals(options.InternalApiKey, DevelopmentInternalApiKey, StringComparison.Ordinal))
            {
                errors.Add($"{ModelServiceOptions.SectionName}:InternalApiKey must be configured with a non-default value outside Development.");
            }
        }

        return errors.Count == 0 ? ValidateOptionsResult.Success : ValidateOptionsResult.Fail(errors);
    }
}
