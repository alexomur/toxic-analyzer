using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Abstractions;

public interface IAnalysisCaptureScheduler
{
    void Schedule(ToxicityAnalysis analysis, CurrentActor actor);

    void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses, CurrentActor actor);
}
