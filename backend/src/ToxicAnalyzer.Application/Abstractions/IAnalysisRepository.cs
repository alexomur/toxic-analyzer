using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Candidates;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Abstractions;

public interface IAnalysisRepository
{
    Task<CandidateText?> FindCandidateTextByFingerprintAsync(
        TextFingerprint fingerprint,
        CancellationToken cancellationToken);

    Task AddCandidateTextAsync(CandidateText candidateText, CancellationToken cancellationToken);

    Task AddAnalysisAsync(ToxicityAnalysis analysis, CancellationToken cancellationToken);

    Task AddAnalysisBatchAsync(AnalysisBatch batch, CancellationToken cancellationToken);
}
