using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Toxicity;

internal static class ToxicityRequestValidation
{
    public static TextContent CreateTextContent(string value, string fieldName)
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

    public static AnalyzeText.AnalyzeTextReportLevel ResolveReportLevel(string? value)
    {
        return value switch
        {
            null => AnalyzeText.AnalyzeTextReportLevel.Summary,
            "summary" => AnalyzeText.AnalyzeTextReportLevel.Summary,
            "full" => AnalyzeText.AnalyzeTextReportLevel.Full,
            _ => throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("reportLevel", "Report level must be either 'summary' or 'full'.")])
        };
    }

    public static void ValidateBatchSize(int count)
    {
        if (count == 0)
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("items", "Batch must contain at least one item.")]);
        }

        if (count > ToxicityApplicationLimits.MaxBatchSize)
        {
            throw new ValidationException(
                "Request validation failed.",
                [new ValidationError("items", $"Batch size must not exceed {ToxicityApplicationLimits.MaxBatchSize}.")]);
        }
    }
}
