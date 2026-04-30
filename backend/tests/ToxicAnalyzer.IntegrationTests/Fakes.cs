using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class FakeModelPredictionClient : IModelPredictionClient
{
    public ModelPrediction SinglePrediction { get; set; } = CreatePrediction(0, 0.12m);

    public ExplainedModelPrediction ExplainedPrediction { get; set; } = CreateExplainedPrediction(0, 0.12m);

    public IReadOnlyList<ModelPrediction> BatchPredictions { get; set; } = [];

    public Exception? ExceptionToThrow { get; set; }

    public int PredictAsyncCallCount { get; private set; }

    public int PredictWithExplanationAsyncCallCount { get; private set; }

    public void Reset()
    {
        SinglePrediction = CreatePrediction(0, 0.12m);
        ExplainedPrediction = CreateExplainedPrediction(0, 0.12m);
        BatchPredictions = [];
        ExceptionToThrow = null;
        PredictAsyncCallCount = 0;
        PredictWithExplanationAsyncCallCount = 0;
    }

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

    public static ModelPrediction CreatePrediction(int label, decimal toxicProbability)
    {
        return new ModelPrediction(
            PredictionLabel.FromInt(label),
            new ToxicProbability(toxicProbability),
            ModelIdentity.Create("baseline", "v3.3"));
    }

    public static ExplainedModelPrediction CreateExplainedPrediction(int label, decimal toxicProbability)
    {
        return new ExplainedModelPrediction(
            CreatePrediction(label, toxicProbability),
            new ModelPredictionExplanation(
                0.89m,
                toxicProbability,
                0.80m,
                [new ModelPredictionFeature("some feature", 0.42m)]));
    }
}

public sealed class FakeClock : IClock
{
    public FakeClock(DateTimeOffset utcNow)
    {
        UtcNow = utcNow;
    }

    public DateTimeOffset UtcNow { get; }
}

public sealed class FakeAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public List<ToxicityAnalysis> CapturedAnalyses { get; } = [];

    public void Reset()
    {
        CapturedAnalyses.Clear();
    }

    public void Schedule(ToxicityAnalysis analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        CapturedAnalyses.Add(analysis);
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        CapturedAnalyses.AddRange(analyses);
    }
}
