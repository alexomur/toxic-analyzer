using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.Application.Toxicity.GetRandomText;

public sealed class GetRandomTextHandler
{
    private readonly IAnalysisTextVotingRepository _repository;

    public GetRandomTextHandler(IAnalysisTextVotingRepository repository)
    {
        _repository = repository;
    }

    public async Task<GetRandomTextResult> HandleAsync(
        GetRandomTextCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var candidate = await _repository.GetRandomAsync(cancellationToken);

        if (candidate is null)
        {
            throw new NotFoundException("No analysis texts are available for voting.");
        }

        return new GetRandomTextResult(candidate.Id.ToString(), candidate.Text);
    }
}
