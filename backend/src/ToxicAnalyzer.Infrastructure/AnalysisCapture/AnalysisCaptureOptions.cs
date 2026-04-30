namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureOptions
{
    public const string SectionName = "AnalysisCapture";

    public bool Enabled { get; set; }

    public string? ConnectionString { get; set; }

    public string Schema { get; set; } = "public";

    public int QueueCapacity { get; set; } = 4096;

    public int BatchSize { get; set; } = 128;

    public TimeSpan FlushInterval { get; set; } = TimeSpan.FromSeconds(2);

    public static bool IsValidSchema(string value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return false;
        }

        if (!(char.IsLetter(value[0]) || value[0] == '_'))
        {
            return false;
        }

        for (var index = 1; index < value.Length; index++)
        {
            var character = value[index];
            if (!(char.IsLetterOrDigit(character) || character == '_'))
            {
                return false;
            }
        }

        return true;
    }
}
