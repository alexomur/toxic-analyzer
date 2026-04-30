using Microsoft.Extensions.Logging;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureChannelScheduler : IAnalysisCaptureScheduler
{
    private const string SourceKind = "public_api";

    private readonly AnalysisCaptureQueue _queue;
    private readonly ILogger<AnalysisCaptureChannelScheduler> _logger;

    public AnalysisCaptureChannelScheduler(
        AnalysisCaptureQueue queue,
        ILogger<AnalysisCaptureChannelScheduler> logger)
    {
        _queue = queue;
        _logger = logger;
    }

    public void Schedule(ToxicityAnalysis analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        TrySchedule(AnalysisCaptureMessage.FromAnalysis(analysis, SourceKind));
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses)
    {
        ArgumentNullException.ThrowIfNull(analyses);

        foreach (var analysis in analyses)
        {
            TrySchedule(AnalysisCaptureMessage.FromAnalysis(analysis, SourceKind));
        }
    }

    private void TrySchedule(AnalysisCaptureMessage message)
    {
        if (_queue.TryWrite(message))
        {
            return;
        }

        _logger.LogWarning(
            "Dropping analysis capture message for fingerprint {TextFingerprint} because the in-memory queue is full.",
            message.TextFingerprint);
    }
}
