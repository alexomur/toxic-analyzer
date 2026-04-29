using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Toxicity.AnalyzeText;

public sealed class AnalyzeTextHandler
{
    private readonly IModelPredictionClient _modelPredictionClient;
    private readonly IClock _clock;

    public AnalyzeTextHandler(
        IModelPredictionClient modelPredictionClient,
        IClock clock)
    {
        _modelPredictionClient = modelPredictionClient;
        _clock = clock;
    }

    public async Task<AnalyzeTextResult> HandleAsync(
        AnalyzeTextCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var text = CreateTextContent(command.Text, "text");
        var reportLevel = ResolveReportLevel(command.ReportLevel);
        var (prediction, explanation) = await PredictAsync(text, reportLevel, cancellationToken);
        var analysis = ToxicityMappings.ToAnalysis(text, prediction, _clock.UtcNow);

        return new AnalyzeTextResult(
            analysis.Id.ToString(),
            analysis.Label.Value,
            analysis.ToxicProbability.Value,
            ToxicityMappings.ToModelDescriptor(analysis.Model),
            reportLevel,
            explanation,
            analysis.CreatedAt);
    }

    private async Task<(ModelPrediction Prediction, AnalyzeTextExplanation? Explanation)> PredictAsync(
        TextContent text,
        AnalyzeTextReportLevel reportLevel,
        CancellationToken cancellationToken)
    {
        if (reportLevel == AnalyzeTextReportLevel.Full)
        {
            var explainedPrediction = await _modelPredictionClient.PredictWithExplanationAsync(text, cancellationToken);
            return (explainedPrediction.Prediction, MapExplanation(explainedPrediction.Explanation));
        }

        var prediction = await _modelPredictionClient.PredictAsync(text, cancellationToken);
        return (prediction, null);
    }

    private static TextContent CreateTextContent(string value, string fieldName)
    {
        try
        {
            return TextContent.Create(value);
        }
        catch (ArgumentException exception)
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError(fieldName, exception.Message)]);
        }
    }

    private static AnalyzeTextReportLevel ResolveReportLevel(string? value)
    {
        return value switch
        {
            null => AnalyzeTextReportLevel.Summary,
            "summary" => AnalyzeTextReportLevel.Summary,
            "full" => AnalyzeTextReportLevel.Full,
            _ => throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("reportLevel", "Report level must be either 'summary' or 'full'.")])
        };
    }

    private static AnalyzeTextExplanation MapExplanation(ModelPredictionExplanation explanation)
    {
        return new AnalyzeTextExplanation(
            explanation.CalibratedProbability,
            explanation.AdjustedProbability,
            explanation.Threshold,
            explanation.Features
                .Select(feature => new AnalyzeTextExplanationFeature(feature.Name, feature.Contribution))
                .ToArray());
    }
}
