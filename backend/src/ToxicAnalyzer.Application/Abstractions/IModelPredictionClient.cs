using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Abstractions;

public interface IModelPredictionClient
{
    Task<ModelPrediction> PredictAsync(TextContent text, CancellationToken cancellationToken);

    Task<IReadOnlyList<ModelPrediction>> PredictBatchAsync(
        IReadOnlyList<TextContent> texts,
        CancellationToken cancellationToken);
}
