using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Abstractions;

public sealed class NoOpAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public void Schedule(ToxicityAnalysis analysis, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentNullException.ThrowIfNull(actor);
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        ArgumentNullException.ThrowIfNull(actor);
    }
}
