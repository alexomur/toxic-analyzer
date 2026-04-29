using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
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
        Assert.Equal(AnalyzeTextReportLevel.Summary, result.ReportLevel);
        Assert.Null(result.Explanation);
        Assert.Equal(fixture.Clock.UtcNow, result.CreatedAt);
    }

    [Fact]
    public async Task HandleAsync_UsesSummaryMode_WhenReportLevelIsOmitted()
    {
        var fixture = TestFixture.Create();

        var result = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Some text"),
            CancellationToken.None);

        Assert.Equal(AnalyzeTextReportLevel.Summary, result.ReportLevel);
        Assert.Equal(1, fixture.ModelClient.PredictAsyncCallCount);
        Assert.Equal(0, fixture.ModelClient.PredictWithExplanationAsyncCallCount);
        Assert.Null(result.Explanation);
    }

    [Fact]
    public async Task HandleAsync_UsesSummaryPrediction_WhenReportLevelIsSummary()
    {
        var fixture = TestFixture.Create();

        var result = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Some text", "summary"),
            CancellationToken.None);

        Assert.Equal(AnalyzeTextReportLevel.Summary, result.ReportLevel);
        Assert.Equal(1, fixture.ModelClient.PredictAsyncCallCount);
        Assert.Equal(0, fixture.ModelClient.PredictWithExplanationAsyncCallCount);
        Assert.Null(result.Explanation);
    }

    [Fact]
    public async Task HandleAsync_UsesExplainPrediction_WhenReportLevelIsFull()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.ExplainedPrediction = TestData.ExplainedPrediction(PredictionLabel.Toxic, 0.91m);

        var result = await fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Some text", "full"),
            CancellationToken.None);

        Assert.Equal(AnalyzeTextReportLevel.Full, result.ReportLevel);
        Assert.Equal(0, fixture.ModelClient.PredictAsyncCallCount);
        Assert.Equal(1, fixture.ModelClient.PredictWithExplanationAsyncCallCount);
        Assert.NotNull(result.Explanation);
        Assert.Equal(0.89m, result.Explanation.CalibratedProbability);
        Assert.Equal(0.91m, result.Explanation.AdjustedProbability);
        Assert.Equal(0.80m, result.Explanation.Threshold);
        Assert.Single(result.Explanation.Features);
    }

    [Fact]
    public async Task HandleAsync_RejectsInvalidReportLevel()
    {
        var fixture = TestFixture.Create();

        var exception = await Assert.ThrowsAsync<ValidationException>(() => fixture.AnalyzeTextHandler.HandleAsync(
            new AnalyzeTextCommand("Some text", "verbose"),
            CancellationToken.None));

        Assert.Contains(exception.Errors, error => error.Field == "reportLevel");
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
