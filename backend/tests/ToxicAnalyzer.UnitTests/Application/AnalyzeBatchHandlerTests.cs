using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Application.Toxicity;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed partial class AnalyzeBatchHandlerTests
{
    [Fact]
    public async Task HandleAsync_ReturnsStatelessBatchAndSummary()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.BatchPredictions =
        [
            TestData.Prediction(PredictionLabel.NonToxic, 0.10m),
            TestData.Prediction(PredictionLabel.Toxic, 0.90m)
        ];

        var result = await fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand(
            [
                new AnalyzeBatchItem("first", "client-1"),
                new AnalyzeBatchItem("second", "client-2")
            ]),
            CancellationToken.None);

        Assert.Equal(2, result.Items.Count);
        Assert.Equal("client-1", result.Items[0].ClientItemId);
        Assert.Equal("client-2", result.Items[1].ClientItemId);
        Assert.Equal(2, result.Summary.Total);
        Assert.Equal(1, result.Summary.ToxicCount);
        Assert.Equal(1, result.Summary.NonToxicCount);
        Assert.Equal(0.50m, result.Summary.AverageToxicProbability);
        Assert.False(string.IsNullOrWhiteSpace(result.BatchId));
        Assert.All(result.Items, item => Assert.False(string.IsNullOrWhiteSpace(item.AnalysisId)));
    }

    [Fact]
    public async Task HandleAsync_PreservesInputOrder()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.BatchPredictions =
        [
            TestData.Prediction(PredictionLabel.Toxic, 0.80m),
            TestData.Prediction(PredictionLabel.NonToxic, 0.20m),
            TestData.Prediction(PredictionLabel.Toxic, 0.70m)
        ];

        var result = await fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand(
            [
                new AnalyzeBatchItem("alpha", "a"),
                new AnalyzeBatchItem("beta", "b"),
                new AnalyzeBatchItem("gamma", "c")
            ]),
            CancellationToken.None);

        Assert.Collection(
            result.Items,
            item => Assert.Equal("a", item.ClientItemId),
            item => Assert.Equal("b", item.ClientItemId),
            item => Assert.Equal("c", item.ClientItemId));
        Assert.Equal([1, 0, 1], result.Items.Select(item => item.Label).ToArray());
    }

    [Fact]
    public async Task HandleAsync_RejectsEmptyBatch()
    {
        var fixture = TestFixture.Create();

        var exception = await Assert.ThrowsAsync<ValidationException>(() => fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand([]),
            CancellationToken.None));

        Assert.Contains(exception.Errors, error => error.Field == "items");
    }

    [Fact]
    public async Task HandleAsync_RejectsBatchLargerThanLimit()
    {
        var fixture = TestFixture.Create();
        var items = Enumerable.Range(0, ToxicityApplicationLimits.MaxBatchSize + 1)
            .Select(index => new AnalyzeBatchItem($"text-{index}", $"item-{index}"))
            .ToArray();

        var exception = await Assert.ThrowsAsync<ValidationException>(() => fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand(items),
            CancellationToken.None));

        Assert.Contains(exception.Errors, error => error.Field == "items");
    }

    [Fact]
    public async Task HandleAsync_PropagatesModelClientErrors()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.ExceptionToThrow = new InvalidOperationException("timeout");

        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand([new AnalyzeBatchItem("text", "a")]),
            CancellationToken.None));
    }

    [Fact]
    public async Task HandleAsync_ThrowsWhenPredictionCountDoesNotMatchInputCount()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.BatchPredictions = [TestData.Prediction(PredictionLabel.Toxic, 0.80m)];

        var exception = await Assert.ThrowsAsync<ToxicAnalyzer.Application.Common.ApplicationException>(() =>
            fixture.AnalyzeBatchHandler.HandleAsync(
                new AnalyzeBatchCommand(
                [
                    new AnalyzeBatchItem("first", "a"),
                    new AnalyzeBatchItem("second", "b")
                ]),
                CancellationToken.None));

        Assert.Equal("Model prediction count does not match the input batch size.", exception.Message);
    }
}
