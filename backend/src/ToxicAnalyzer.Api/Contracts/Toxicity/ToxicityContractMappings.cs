using ToxicAnalyzer.Application.Toxicity;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;
using ToxicAnalyzer.Application.Toxicity.GetTextById;

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
            ToReportLevelResponse(result.ReportLevel),
            ToExplanationResponse(result.Explanation),
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

    public static GetRandomTextResponse ToResponse(this GetRandomTextResult result)
    {
        return new GetRandomTextResponse(result.TextId, result.Text);
    }

    public static GetTextByIdResponse ToResponse(this GetTextByIdResult result)
    {
        return new GetTextByIdResponse(
            result.TextId,
            result.Text,
            result.TextLength,
            result.RequestCount,
            result.LastLabel,
            result.LastToxicProbability,
            new ModelInfoResponse(result.LastModelKey, result.LastModelVersion),
            result.VotesToxic,
            result.VotesNonToxic,
            result.CreatedAt,
            result.LastSeenAt);
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

    private static string ToReportLevelResponse(AnalyzeTextReportLevel reportLevel)
    {
        return reportLevel switch
        {
            AnalyzeTextReportLevel.Summary => "summary",
            AnalyzeTextReportLevel.Full => "full",
            _ => throw new ArgumentOutOfRangeException(nameof(reportLevel), reportLevel, "Unsupported report level.")
        };
    }

    private static AnalyzeTextExplanationResponse? ToExplanationResponse(AnalyzeTextExplanation? explanation)
    {
        if (explanation is null)
        {
            return null;
        }

        return new AnalyzeTextExplanationResponse(
            explanation.CalibratedProbability,
            explanation.AdjustedProbability,
            explanation.Threshold,
            explanation.Features
                .Select(feature => new AnalyzeTextExplanationFeatureResponse(feature.Name, feature.Contribution))
                .ToArray());
    }
}
