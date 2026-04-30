using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureBackgroundService : BackgroundService
{
    private readonly AnalysisCaptureQueue _queue;
    private readonly IAnalysisTextStore _store;
    private readonly AnalysisCaptureOptions _options;
    private readonly ILogger<AnalysisCaptureBackgroundService> _logger;

    public AnalysisCaptureBackgroundService(
        AnalysisCaptureQueue queue,
        IAnalysisTextStore store,
        IOptions<AnalysisCaptureOptions> options,
        ILogger<AnalysisCaptureBackgroundService> logger)
    {
        _queue = queue;
        _store = store;
        _options = options.Value;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var buffer = new List<AnalysisCaptureMessage>(_options.BatchSize);

        while (!stoppingToken.IsCancellationRequested)
        {
            buffer.Clear();

            if (!await TryFillBufferAsync(buffer, stoppingToken))
            {
                break;
            }

            try
            {
                var records = AnalysisTextBatchAggregator.Aggregate(buffer);
                await _store.UpsertAsync(records, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception exception)
            {
                _logger.LogError(
                    exception,
                    "Failed to persist analysis capture batch of {BatchSize} messages. The batch will be dropped.",
                    buffer.Count);
            }
        }
    }

    private async Task<bool> TryFillBufferAsync(List<AnalysisCaptureMessage> buffer, CancellationToken cancellationToken)
    {
        if (!await _queue.Reader.WaitToReadAsync(cancellationToken))
        {
            return false;
        }

        while (_queue.Reader.TryRead(out var message))
        {
            buffer.Add(message);
            if (buffer.Count >= _options.BatchSize)
            {
                return true;
            }
        }

        using var flushDelay = new CancellationTokenSource(_options.FlushInterval);
        using var linkedTokenSource = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken, flushDelay.Token);

        while (buffer.Count < _options.BatchSize)
        {
            try
            {
                if (!await _queue.Reader.WaitToReadAsync(linkedTokenSource.Token))
                {
                    return buffer.Count > 0;
                }
            }
            catch (OperationCanceledException) when (!cancellationToken.IsCancellationRequested)
            {
                return buffer.Count > 0;
            }

            while (_queue.Reader.TryRead(out var message))
            {
                buffer.Add(message);
                if (buffer.Count >= _options.BatchSize)
                {
                    return true;
                }
            }
        }

        return true;
    }
}
