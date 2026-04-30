using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Abstractions;

public sealed class NoOpAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public void Schedule(ToxicityAnalysis analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses)
    {
        ArgumentNullException.ThrowIfNull(analyses);
    }
}
