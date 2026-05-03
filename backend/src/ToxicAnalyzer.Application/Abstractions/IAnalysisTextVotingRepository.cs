namespace ToxicAnalyzer.Application.Abstractions;

public interface IAnalysisTextVotingRepository
{
    Task<Guid?> EnsureVoteableTextAsync(
        Domain.Analysis.ToxicityAnalysis analysis,
        AnalysisTextOrigin origin,
        CurrentActor actor,
        CancellationToken cancellationToken);

    Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken);

    Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken);

    Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CurrentActor actor, CancellationToken cancellationToken);
}
