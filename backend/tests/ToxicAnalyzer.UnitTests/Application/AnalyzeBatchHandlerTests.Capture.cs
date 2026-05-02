using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed partial class AnalyzeBatchHandlerTests
{
    [Fact]
    public async Task HandleAsync_SchedulesCapturedAnalyses_ForValidatedBatch()
    {
        var fixture = TestFixture.Create();
        fixture.ModelClient.BatchPredictions =
        [
            TestData.Prediction(ToxicAnalyzer.Domain.Analysis.PredictionLabel.NonToxic, 0.10m),
            TestData.Prediction(ToxicAnalyzer.Domain.Analysis.PredictionLabel.Toxic, 0.90m)
        ];

        await fixture.AnalyzeBatchHandler.HandleAsync(
            new AnalyzeBatchCommand(
            [
                new AnalyzeBatchItem("first", null),
                new AnalyzeBatchItem("second", null)
            ]),
            CancellationToken.None);

        Assert.Equal(2, fixture.AnalysisCaptureScheduler.CapturedAnalyses.Count);
        Assert.Equal(["first", "second"], fixture.AnalysisCaptureScheduler.CapturedAnalyses.Select(item => item.Analysis.Text.Original).ToArray());
    }
}
