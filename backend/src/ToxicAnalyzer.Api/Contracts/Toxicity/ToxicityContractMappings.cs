using ToxicAnalyzer.Application.Toxicity;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;

namespace ToxicAnalyzer.Api.Contracts.Toxicity;

internal static class ToxicityContractMappings
{
    public static AnalyzeTextResponse ToResponse(this AnalyzeTextResult result)
    {
        return new AnalyzeTextResponse(
            result.AnalysisId,
            result.Label,
            result.ToxicProbability,
            ToModelResponse(result.Model),
            result.CreatedAt);
    }

    public static AnalyzeBatchResponse ToResponse(this AnalyzeBatchResult result)
    {
        return new AnalyzeBatchResponse(
            result.BatchId,
            result.Items.Select(ToBatchItemResponse).ToArray(),
            ToSummaryResponse(result.Summary),
            result.CreatedAt);
    }

    private static AnalyzeBatchItemResponse ToBatchItemResponse(AnalyzeBatchResultItem item)
    {
        return new AnalyzeBatchItemResponse(
            item.ClientItemId,
            item.AnalysisId,
            item.Label,
            item.ToxicProbability,
            ToModelResponse(item.Model));
    }

    private static BatchSummaryResponse ToSummaryResponse(BatchSummaryModel summary)
    {
        return new BatchSummaryResponse(
            summary.Total,
            summary.ToxicCount,
            summary.NonToxicCount,
            summary.AverageToxicProbability);
    }

    private static ModelInfoResponse ToModelResponse(ModelDescriptor model)
    {
        return new ModelInfoResponse(model.ModelKey, model.ModelVersion);
    }
}
