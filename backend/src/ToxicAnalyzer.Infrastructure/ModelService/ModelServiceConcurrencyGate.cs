using Microsoft.Extensions.Options;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceConcurrencyGate
{
    private readonly SemaphoreSlim _semaphore;

    public ModelServiceConcurrencyGate(IOptions<ModelServiceOptions> options)
    {
        _semaphore = new SemaphoreSlim(options.Value.MaxConcurrentRequests, options.Value.MaxConcurrentRequests);
    }

    public async Task<IDisposable> AcquireAsync(CancellationToken cancellationToken)
    {
        await _semaphore.WaitAsync(cancellationToken);
        return new Releaser(_semaphore);
    }

    private sealed class Releaser : IDisposable
    {
        private readonly SemaphoreSlim _semaphore;
        private bool _disposed;

        public Releaser(SemaphoreSlim semaphore)
        {
            _semaphore = semaphore;
        }

        public void Dispose()
        {
            if (_disposed)
            {
                return;
            }

            _semaphore.Release();
            _disposed = true;
        }
    }
}
