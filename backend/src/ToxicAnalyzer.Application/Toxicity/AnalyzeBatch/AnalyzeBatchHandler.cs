using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;

public sealed class AnalyzeBatchHandler
{
    private readonly IModelPredictionClient _modelPredictionClient;
    private readonly IAnalysisCaptureScheduler _analysisCaptureScheduler;
    private readonly ICurrentActorAccessor _currentActorAccessor;
    private readonly IClock _clock;

    public AnalyzeBatchHandler(
        IModelPredictionClient modelPredictionClient,
        IAnalysisCaptureScheduler analysisCaptureScheduler,
        ICurrentActorAccessor currentActorAccessor,
        IClock clock)
    {
        _modelPredictionClient = modelPredictionClient;
        _analysisCaptureScheduler = analysisCaptureScheduler;
        _currentActorAccessor = currentActorAccessor;
        _clock = clock;
    }

    public async Task<AnalyzeBatchResult> HandleAsync(
        AnalyzeBatchCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);
        ValidateBatch(command);

        var validatedItems = command.Items
            .Select((item, index) => new ValidatedBatchItem(
                index,
                ToxicityRequestValidation.CreateTextContent(item.Text, $"items[{index}].text"),
                item.ClientItemId))
            .ToArray();

        var predictions = await _modelPredictionClient.PredictBatchAsync(
            validatedItems.Select(item => item.Text).ToArray(),
            cancellationToken);

        if (predictions.Count != validatedItems.Length)
        {
            throw new Common.ApplicationException("Model prediction count does not match the input batch size.");
        }

        var createdAt = _clock.UtcNow;
        var analysisItems = new AnalysisBatchItem[validatedItems.Length];
        var resultItems = new AnalyzeBatchResultItem[validatedItems.Length];

        for (var index = 0; index < validatedItems.Length; index++)
        {
            var validatedItem = validatedItems[index];
            var analysis = ToxicityMappings.ToAnalysis(validatedItem.Text, predictions[index], createdAt);

            analysisItems[index] = ToxicityMappings.ToBatchItem(index, analysis, validatedItem.ClientItemId);
            resultItems[index] = new AnalyzeBatchResultItem(
                validatedItem.ClientItemId,
                analysis.Id.ToString(),
                analysis.Label.Value,
                analysis.ToxicProbability.Value,
                ToxicityMappings.ToModelDescriptor(analysis.Model));
        }

        var batch = Domain.Analysis.AnalysisBatch.Create(analysisItems, createdAt);
        var actor = _currentActorAccessor.GetCurrent();
        _analysisCaptureScheduler.ScheduleBatch(analysisItems.Select(item => item.Analysis).ToArray(), actor);

        return new AnalyzeBatchResult(
            batch.Id.ToString(),
            resultItems,
            ToxicityMappings.ToBatchSummary(batch.Summary),
            batch.CreatedAt);
    }

    private static void ValidateBatch(AnalyzeBatchCommand command)
    {
        if (command.Items is null)
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("items", "Batch items are required.")]);
        }

        ToxicityRequestValidation.ValidateBatchSize(command.Items.Count);
    }

    private sealed record ValidatedBatchItem(int Position, TextContent Text, string? ClientItemId);
}
