using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class DisabledAnalysisTextVotingRepository : IAnalysisTextVotingRepository
{
    public Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken)
    {
        throw new ToxicAnalyzer.Application.Common.ApplicationException(
            "Analysis text voting is unavailable because AnalysisCapture is disabled.");
    }

    public Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
    {
        throw new ToxicAnalyzer.Application.Common.ApplicationException(
            "Analysis text voting is unavailable because AnalysisCapture is disabled.");
    }

    public Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CurrentActor actor, CancellationToken cancellationToken)
    {
        throw new ToxicAnalyzer.Application.Common.ApplicationException(
            "Analysis text voting is unavailable because AnalysisCapture is disabled.");
    }
}
