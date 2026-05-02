using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Application.Toxicity.VoteText;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed class VoteTextHandlerTests
{
    [Fact]
    public async Task HandleAsync_RegistersToxicVote()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();

        await fixture.VoteTextHandler.HandleAsync(
            new VoteTextCommand(textId, "toxic"),
            CancellationToken.None);

        Assert.Single(fixture.AnalysisTextVotingRepository.RegisteredVotes);
        Assert.Equal(textId, fixture.AnalysisTextVotingRepository.RegisteredVotes[0].Id);
        Assert.Equal(AnalysisTextVoteKind.Toxic, fixture.AnalysisTextVotingRepository.RegisteredVotes[0].Vote);
    }

    [Fact]
    public async Task HandleAsync_RegistersNonToxicVote()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();

        await fixture.VoteTextHandler.HandleAsync(
            new VoteTextCommand(textId, "nonToxic"),
            CancellationToken.None);

        Assert.Single(fixture.AnalysisTextVotingRepository.RegisteredVotes);
        Assert.Equal(textId, fixture.AnalysisTextVotingRepository.RegisteredVotes[0].Id);
        Assert.Equal(AnalysisTextVoteKind.NonToxic, fixture.AnalysisTextVotingRepository.RegisteredVotes[0].Vote);
    }

    [Fact]
    public async Task HandleAsync_ThrowsValidationException_ForUnsupportedVote()
    {
        var fixture = TestFixture.Create();

        var exception = await Assert.ThrowsAsync<ValidationException>(() =>
            fixture.VoteTextHandler.HandleAsync(
                new VoteTextCommand(Guid.NewGuid(), "maybe"),
                CancellationToken.None));

        Assert.Contains(exception.Errors, error => error.Field == "vote");
    }

    [Fact]
    public async Task HandleAsync_ThrowsNotFound_WhenTextDoesNotExist()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();
        fixture.AnalysisTextVotingRepository.RegisterVoteResult = false;

        var exception = await Assert.ThrowsAsync<NotFoundException>(() =>
            fixture.VoteTextHandler.HandleAsync(
                new VoteTextCommand(textId, "toxic"),
                CancellationToken.None));

        Assert.Equal($"Analysis text '{textId}' was not found.", exception.Message);
    }
}
