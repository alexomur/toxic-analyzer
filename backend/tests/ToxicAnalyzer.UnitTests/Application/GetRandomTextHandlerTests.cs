using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed class GetRandomTextHandlerTests
{
    [Fact]
    public async Task HandleAsync_ReturnsRandomText_WhenRepositoryHasCandidate()
    {
        var fixture = TestFixture.Create();
        var textId = Guid.NewGuid();
        fixture.AnalysisTextVotingRepository.RandomCandidate = new(textId, "stored text");

        var result = await fixture.GetRandomTextHandler.HandleAsync(new GetRandomTextCommand(), CancellationToken.None);

        Assert.Equal(textId.ToString(), result.TextId);
        Assert.Equal("stored text", result.Text);
    }

    [Fact]
    public async Task HandleAsync_ThrowsNotFound_WhenRepositoryReturnsNull()
    {
        var fixture = TestFixture.Create();

        var exception = await Assert.ThrowsAsync<NotFoundException>(() =>
            fixture.GetRandomTextHandler.HandleAsync(new GetRandomTextCommand(), CancellationToken.None));

        Assert.Equal("No analysis texts are available for voting.", exception.Message);
    }
}
