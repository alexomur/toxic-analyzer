using Microsoft.Extensions.Logging;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureChannelScheduler : IAnalysisCaptureScheduler
{
    private readonly AnalysisCaptureQueue _queue;
    private readonly ILogger<AnalysisCaptureChannelScheduler> _logger;

    public AnalysisCaptureChannelScheduler(
        AnalysisCaptureQueue queue,
        ILogger<AnalysisCaptureChannelScheduler> logger)
    {
        _queue = queue;
        _logger = logger;
    }

    public void Schedule(ToxicityAnalysis analysis, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentNullException.ThrowIfNull(actor);
        TrySchedule(AnalysisCaptureMessage.FromAnalysis(analysis, actor.SourceKind, actor.SubjectId, actor.TenantId));
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        ArgumentNullException.ThrowIfNull(actor);

        foreach (var analysis in analyses)
        {
            TrySchedule(AnalysisCaptureMessage.FromAnalysis(analysis, actor.SourceKind, actor.SubjectId, actor.TenantId));
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
