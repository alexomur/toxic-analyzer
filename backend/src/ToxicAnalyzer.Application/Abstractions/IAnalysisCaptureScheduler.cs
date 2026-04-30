using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Abstractions;

public interface IAnalysisCaptureScheduler
{
    void Schedule(ToxicityAnalysis analysis);

    void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses);
}
