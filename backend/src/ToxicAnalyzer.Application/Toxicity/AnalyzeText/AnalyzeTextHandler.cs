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
        var prediction = await _modelPredictionClient.PredictAsync(text, cancellationToken);
        var analysis = ToxicityMappings.ToAnalysis(text, prediction, _clock.UtcNow);

        return new AnalyzeTextResult(
            analysis.Id.ToString(),
            analysis.Label.Value,
            analysis.ToxicProbability.Value,
            ToxicityMappings.ToModelDescriptor(analysis.Model),
            analysis.CreatedAt);
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
}
