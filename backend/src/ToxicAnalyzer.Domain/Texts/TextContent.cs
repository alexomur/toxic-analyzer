using ToxicAnalyzer.Domain.Common;

namespace ToxicAnalyzer.Domain.Texts;

public sealed record TextContent
{
    private TextContent(string original, string normalized)
    {
        Original = original;
        Normalized = normalized;
    }

    public string Original { get; }

    public string Normalized { get; }

    public static TextContent Create(string value)
    {
        ArgumentNullException.ThrowIfNull(value);

        var normalized = Normalize(value);
        if (normalized.Length == 0)
        {
            throw new ArgumentException("Text must not be blank.", nameof(value));
        }

        return new TextContent(value, normalized);
    }

    private static string Normalize(string value)
    {
        return value
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Replace('\r', '\n')
            .Trim();
    }

    public override string ToString() => Original;
}
