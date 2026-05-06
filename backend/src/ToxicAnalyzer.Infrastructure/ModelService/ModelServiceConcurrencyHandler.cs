namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceConcurrencyHandler : DelegatingHandler
{
    private readonly ModelServiceConcurrencyGate _gate;

    public ModelServiceConcurrencyHandler(ModelServiceConcurrencyGate gate)
    {
        _gate = gate;
    }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request,
        CancellationToken cancellationToken)
    {
        using var lease = await _gate.AcquireAsync(cancellationToken);
        return await base.SendAsync(request, cancellationToken);
    }
}
