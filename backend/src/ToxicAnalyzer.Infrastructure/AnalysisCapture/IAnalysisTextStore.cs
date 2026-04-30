namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public interface IAnalysisTextStore
{
    Task UpsertAsync(IReadOnlyList<AnalysisTextUpsertRecord> records, CancellationToken cancellationToken);
}
