using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed class AnalyzeTextHandlerTests
{
    [Fact]
    public async Task HandleAsync_ReturnsStatelessAnalysisResult_WhenRequestIsValid()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.SinglePrediction = TestData.Prediction(PredictionLabel.Toxic, 0.91m);

        var result = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("You are awful"),
            CancellationToken.None);

        Assert.False(string.IsNullOrWhiteSpace(result.AnalysisId));
        Assert.Equal(1, result.Label);
        Assert.Equal(0.91m, result.ToxicProbability);
        Assert.Equal("baseline-a", result.Model.ModelKey);
        Assert.Equal("v1", result.Model.ModelVersion);
        Assert.Equal(fixture.Clock.UtcNow, result.CreatedAt);
    }

    [Fact]
    public async Task HandleAsync_GeneratesDistinctAnalysisIdsAcrossCalls()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.SinglePrediction = TestData.Prediction(PredictionLabel.NonToxic, 0.15m);

        var first = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Same text"),
            CancellationToken.None);
        var second = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Same text"),
            CancellationToken.None);

        Assert.NotEqual(first.AnalysisId, second.AnalysisId);
    }

    [Fact]
    public async Task HandleAsync_PropagatesModelClientErrors()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.ExceptionToThrow = new InvalidOperationException("upstream error");

        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Some text"),
            CancellationToken.None));
    }
}
