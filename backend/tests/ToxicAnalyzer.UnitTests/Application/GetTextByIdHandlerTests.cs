using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Application.Toxicity.GetTextById;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed class GetTextByIdHandlerTests
{
    [Fact]
    public async Task HandleAsync_ReturnsStoredVotingDetails()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();
        fixture.AnalysisTextVotingRepository.Details = new AnalysisTextVotingDetails(
            textId,
            "stored text",
            11,
            4,
            1,
            0.87m,
            "baseline",
            "v3.3",
            1,
            2,
            new DateTimeOffset(2026, 5, 2, 9, 0, 0, TimeSpan.Zero),
            new DateTimeOffset(2026, 5, 2, 10, 0, 0, TimeSpan.Zero));

        var result = await fixture.GetTextByIdHandler.HandleAsync(
            new GetTextByIdCommand(textId),
            CancellationToken.None);

        Assert.Equal(textId.ToString(), result.TextId);
        Assert.Equal("stored text", result.Text);
        Assert.Equal(11, result.TextLength);
        Assert.Equal(4, result.RequestCount);
        Assert.Equal(1, result.LastLabel);
        Assert.Equal(0.87m, result.LastToxicProbability);
        Assert.Equal("baseline", result.LastModelKey);
        Assert.Equal("v3.3", result.LastModelVersion);
        Assert.Equal(1, result.VotesToxic);
        Assert.Equal(2, result.VotesNonToxic);
    }

    [Fact]
    public async Task HandleAsync_ThrowsNotFound_WhenTextDoesNotExist()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();

        var exception = await Assert.ThrowsAsync<NotFoundException>(() =>
            fixture.GetTextByIdHandler.HandleAsync(
                new GetTextByIdCommand(textId),
                CancellationToken.None));

        Assert.Equal($"Analysis text '{textId}' was not found.", exception.Message);
    }
}
