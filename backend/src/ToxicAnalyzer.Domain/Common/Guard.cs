namespace ToxicAnalyzer.Domain.Common;

internal static class Guard
{
    public static string AgainstNullOrWhiteSpace(string? value, string paramName)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new ArgumentException("Value cannot be null, empty, or whitespace.", paramName);
        }

        return value;
    }

    public static DateTimeOffset AgainstDefault(DateTimeOffset value, string paramName)
    {
        if (value == default)
        {
            throw new ArgumentException("Value must be specified.", paramName);
        }

        return value;
    }
}
