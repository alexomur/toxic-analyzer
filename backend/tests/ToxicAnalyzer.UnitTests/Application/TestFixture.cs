using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.UnitTests.Application;

internal sealed class TestFixture
{
    private TestFixture(
        FakeModelPredictionClient modelClient,
        FakeClock clock)
    {
        ModelClient = modelClient;
        Clock = clock;
        AnalyzeTextHandler = new AnalyzeTextHandler(modelClient, clock);
        AnalyzeBatchHandler = new AnalyzeBatchHandler(modelClient, clock);
    }

    public FakeModelPredictionClient ModelClient { get; }

    public FakeClock Clock { get; }

    public AnalyzeTextHandler AnalyzeTextHandler { get; }

    public AnalyzeBatchHandler AnalyzeBatchHandler { get; }

    public static TestFixture Create()
    {
        var modelClient = new FakeModelPredictionClient();
        var clock = new FakeClock(new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero));
        return new TestFixture(modelClient, clock);
    }
}

internal sealed class FakeModelPredictionClient : IModelPredictionClient
{
    public ModelPrediction SinglePrediction { get; set; } = TestData.Prediction(PredictionLabel.NonToxic, 0.05m);

    public ExplainedModelPrediction ExplainedPrediction { get; set; } = TestData.ExplainedPrediction(PredictionLabel.NonToxic, 0.05m);

    public IReadOnlyList<ModelPrediction> BatchPredictions { get; set; } = [];

    public Exception? ExceptionToThrow { get; set; }

    public int PredictAsyncCallCount { get; private set; }

    public int PredictWithExplanationAsyncCallCount { get; private set; }

    public Task<ModelPrediction> PredictAsync(TextContent text, CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        PredictAsyncCallCount++;
        return Task.FromResult(SinglePrediction);
    }

    public Task<ExplainedModelPrediction> PredictWithExplanationAsync(
        TextContent text,
        CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        PredictWithExplanationAsyncCallCount++;
        return Task.FromResult(ExplainedPrediction);
    }

    public Task<IReadOnlyList<ModelPrediction>> PredictBatchAsync(
        IReadOnlyList<TextContent> texts,
        CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        return Task.FromResult(BatchPredictions);
    }
}

internal sealed class FakeClock : IClock
{
    public FakeClock(DateTimeOffset utcNow)
    {
        UtcNow = utcNow;
    }

    public DateTimeOffset UtcNow { get; }
}

internal static class TestData
{
    public static ModelPrediction Prediction(PredictionLabel label, decimal probability)
    {
        return new ModelPrediction(
            label,
            new ToxicProbability(probability),
            ModelIdentity.Create("baseline-a", "v1"));
    }

    public static ExplainedModelPrediction ExplainedPrediction(PredictionLabel label, decimal probability)
    {
        return new ExplainedModelPrediction(
            Prediction(label, probability),
            new ModelPredictionExplanation(
                0.89m,
                probability,
                0.80m,
                [new ModelPredictionFeature("strong_insult_count", 0.42m)]));
    }

    public static ToxicityAnalysis Analysis(
        string text,
        PredictionLabel label,
        decimal probability,
        DateTimeOffset createdAt)
    {
        return ToxicityAnalysis.Create(
            TextContent.Create(text),
            label,
            new ToxicProbability(probability),
            ModelIdentity.Create("baseline-a", "v1"),
            createdAt);
    }
}
