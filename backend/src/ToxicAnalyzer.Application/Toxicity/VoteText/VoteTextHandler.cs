using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Toxicity.VoteText;

public sealed class VoteTextHandler
{
    private readonly IAnalysisTextVotingRepository _repository;
    private readonly ICurrentActorAccessor _currentActorAccessor;

    public VoteTextHandler(
        IAnalysisTextVotingRepository repository,
        ICurrentActorAccessor currentActorAccessor)
    {
        _repository = repository;
        _currentActorAccessor = currentActorAccessor;
    }

    public async Task HandleAsync(
        VoteTextCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var vote = ResolveVote(command.Vote);
        var actor = _currentActorAccessor.GetCurrent();
        var updated = await _repository.RegisterVoteAsync(command.TextId, vote, actor, cancellationToken);

        if (!updated)
        {
            throw new NotFoundException($"Analysis text '{command.TextId}' was not found.");
        }
    }

    private static AnalysisTextVoteKind ResolveVote(string value)
    {
        return value switch
        {
            "toxic" => AnalysisTextVoteKind.Toxic,
            "nonToxic" => AnalysisTextVoteKind.NonToxic,
            _ => throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("vote", "Vote must be either 'toxic' or 'nonToxic'.")])
        };
    }
}
