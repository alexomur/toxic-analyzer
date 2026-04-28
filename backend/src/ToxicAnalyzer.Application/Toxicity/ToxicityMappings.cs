using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Toxicity;

internal static class ToxicityMappings
{
    public static AnalysisResultModel ToAnalysisResult(ToxicityAnalysis analysis)
    {
        return new AnalysisResultModel(
            analysis.Id.ToString(),
            analysis.Label.Value,
            analysis.ToxicProbability.Value,
            ToModelDescriptor(analysis.Model),
            analysis.CreatedAt);
    }

    public static ModelDescriptor ToModelDescriptor(ModelIdentity model)
    {
        return new ModelDescriptor(model.ModelKey, model.ModelVersion);
    }

    public static AnalysisBatchItem ToBatchItem(
        int position,
        ToxicityAnalysis analysis,
        string? clientItemId)
    {
        return Domain.Analysis.AnalysisBatchItem.Create(
            position,
            analysis,
            clientItemId is null ? null : ClientItemId.Create(clientItemId));
    }

    public static ToxicityAnalysis ToAnalysis(
        Domain.Texts.TextContent text,
        ModelPrediction prediction,
        DateTimeOffset createdAt)
    {
        return Domain.Analysis.ToxicityAnalysis.Create(
            text,
            prediction.Label,
            prediction.ToxicProbability,
            prediction.Model,
            createdAt);
    }

    public static BatchSummaryModel ToBatchSummary(AnalysisBatchSummary summary)
    {
        return new BatchSummaryModel(
            summary.Total,
            summary.ToxicCount,
            summary.NonToxicCount,
            summary.AverageToxicProbability);
    }
}
