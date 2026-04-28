using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class FakeModelPredictionClient : IModelPredictionClient
{
    public ModelPrediction SinglePrediction { get; set; } = CreatePrediction(0, 0.12m);

    public IReadOnlyList<ModelPrediction> BatchPredictions { get; set; } = [];

    public Exception? ExceptionToThrow { get; set; }

    public Task<ModelPrediction> PredictAsync(TextContent text, CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        return Task.FromResult(SinglePrediction);
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
}

public sealed class FakeClock : IClock
{
    public FakeClock(DateTimeOffset utcNow)
    {
        UtcNow = utcNow;
    }

    public DateTimeOffset UtcNow { get; }
}
