using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;
using ToxicAnalyzer.Infrastructure.AnalysisCapture;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class AnalysisTextBatchAggregatorTests
{
    [Fact]
    public void Aggregate_CollapsesDuplicateFingerprints_AndKeepsLatestModelSnapshot()
    {
        var firstText = TextContent.Create("  same text\r\n");
        var secondText = TextContent.Create("same text");

        var records = AnalysisTextBatchAggregator.Aggregate(
        [
            AnalysisCaptureMessage.FromAnalysis(
                ToxicityAnalysis.Create(
                    firstText,
                    PredictionLabel.NonToxic,
                    new ToxicProbability(0.20m),
                    ModelIdentity.Create("baseline-a", "v1"),
                    new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero)),
                "public_api"),
            AnalysisCaptureMessage.FromAnalysis(
                ToxicityAnalysis.Create(
                    secondText,
                    PredictionLabel.Toxic,
                    new ToxicProbability(0.85m),
                    ModelIdentity.Create("baseline-a", "v2"),
                    new DateTimeOffset(2026, 4, 29, 12, 5, 0, TimeSpan.Zero)),
                "public_api")
        ]);

        var record = Assert.Single(records);
        Assert.Equal("same text", record.NormalizedText);
        Assert.Equal(2, record.RequestCount);
        Assert.Equal(1, record.LastLabel);
        Assert.Equal(0.85m, record.LastToxicProbability);
        Assert.Equal("v2", record.LastModelVersion);
    }
}
