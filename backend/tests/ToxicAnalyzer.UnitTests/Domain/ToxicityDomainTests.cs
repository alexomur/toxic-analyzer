using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Candidates;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.UnitTests.Domain;

public sealed class ToxicityDomainTests
{
    [Fact]
    public void TextContent_Create_NormalizesLineEndingsAndTrims() 
    {
        var text = TextContent.Create("  first line\r\nsecond line  ");

        Assert.Equal("first line\nsecond line", text.Normalized);
        Assert.Equal("  first line\r\nsecond line  ", text.Original);
    }

    [Fact]
    public void AnalysisBatch_Create_ComputesSummaryAndPreservesClientIds()
    {
        var createdAt = new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero);
        var model = ModelIdentity.Create("baseline-a", "v3.3");

        var firstAnalysis = ToxicityAnalysis.Create(
            TextContent.Create("calm"),
            PredictionLabel.NonToxic,
            new ToxicProbability(0.10m),
            model,
            createdAt);

        var secondAnalysis = ToxicityAnalysis.Create(
            TextContent.Create("toxic"),
            PredictionLabel.Toxic,
            new ToxicProbability(0.90m),
            model,
            createdAt);

        var batch = AnalysisBatch.Create(
            [
                AnalysisBatchItem.Create(0, firstAnalysis, ClientItemId.Create("a")),
                AnalysisBatchItem.Create(1, secondAnalysis, ClientItemId.Create("b"))
            ],
            createdAt);

        Assert.Equal(2, batch.Summary.Total);
        Assert.Equal(1, batch.Summary.ToxicCount);
        Assert.Equal(1, batch.Summary.NonToxicCount);
        Assert.Equal(0.50m, batch.Summary.AverageToxicProbability);
        Assert.Equal("a", batch.Items[0].ClientItemId!.Value);
        Assert.Equal("b", batch.Items[1].ClientItemId!.Value);
    }

    [Fact]
    public void CandidateText_RegisterAnalysis_UpdatesLatestSnapshotForMatchingText()
    {
        var firstCreatedAt = new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero);
        var secondCreatedAt = firstCreatedAt.AddMinutes(5);

        var firstAnalysis = ToxicityAnalysis.Create(
            TextContent.Create("You are rude"),
            PredictionLabel.NonToxic,
            new ToxicProbability(0.30m),
            ModelIdentity.Create("baseline-a", "v3.2"),
            firstCreatedAt);

        var secondAnalysis = ToxicityAnalysis.Create(
            TextContent.Create("You are rude"),
            PredictionLabel.Toxic,
            new ToxicProbability(0.82m),
            ModelIdentity.Create("baseline-a", "v3.3"),
            secondCreatedAt);

        var candidate = CandidateText.CreateFromAnalysis(firstAnalysis);
        candidate.RegisterAnalysis(secondAnalysis);

        Assert.Equal(2, candidate.AnalysisCount);
        Assert.Equal(secondCreatedAt, candidate.LastSeenAt);
        Assert.Equal(secondAnalysis.Id, candidate.LastAnalysisId);
        Assert.Equal(PredictionLabel.Toxic, candidate.LastLabel);
        Assert.Equal(0.82m, candidate.LastToxicProbability.Value);
        Assert.Equal("v3.3", candidate.LastModel.ModelVersion);
    }
}
