namespace ToxicAnalyzer.Application.Abstractions;

public interface IAnalysisTextVotingRepository
{
    Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken);

    Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CancellationToken cancellationToken);
}
