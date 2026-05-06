using Microsoft.Extensions.Options;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceAuthenticationHandler : DelegatingHandler
{
    private readonly ModelServiceOptions _options;

    public ModelServiceAuthenticationHandler(IOptions<ModelServiceOptions> options)
    {
        _options = options.Value;
    }

    protected override Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        if (!string.IsNullOrWhiteSpace(_options.InternalApiKey))
        {
            request.Headers.Remove(_options.InternalApiKeyHeaderName);
            request.Headers.Add(_options.InternalApiKeyHeaderName, _options.InternalApiKey);
        }

        return base.SendAsync(request, cancellationToken);
    }
}
