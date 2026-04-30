using System.Threading.Channels;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureQueue
{
    private readonly Channel<AnalysisCaptureMessage> _channel;

    public AnalysisCaptureQueue(int capacity)
    {
        if (capacity <= 0)
        {
            throw new ArgumentOutOfRangeException(nameof(capacity), capacity, "Queue capacity must be greater than zero.");
        }

        _channel = Channel.CreateBounded<AnalysisCaptureMessage>(new BoundedChannelOptions(capacity)
        {
            FullMode = BoundedChannelFullMode.DropWrite,
            SingleReader = true,
            SingleWriter = false
        });
    }

    public ChannelReader<AnalysisCaptureMessage> Reader => _channel.Reader;

    public bool TryWrite(AnalysisCaptureMessage message)
    {
        return _channel.Writer.TryWrite(message);
    }
}
