using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Toxicity.GetTextById;

public sealed class GetTextByIdHandler
{
    private readonly IAnalysisTextVotingRepository _repository;

    public GetTextByIdHandler(IAnalysisTextVotingRepository repository)
    {
        _repository = repository;
    }

    public async Task<GetTextByIdResult> HandleAsync(
        GetTextByIdCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var details = await _repository.GetByIdAsync(command.TextId, cancellationToken);

        if (details is null)
        {
            throw new NotFoundException($"Analysis text '{command.TextId}' was not found.");
        }

        return new GetTextByIdResult(
            details.Id.ToString(),
            details.Text,
            details.TextLength,
            details.RequestCount,
            details.LastLabel,
            details.LastToxicProbability,
            details.LastModelKey,
            details.LastModelVersion,
            details.VotesToxic,
            details.VotesNonToxic,
            details.CreatedAt,
            details.LastSeenAt);
    }
}
