using ToxicAnalyzer.Domain.Common;

namespace ToxicAnalyzer.Domain.Analysis;

public sealed record ClientItemId
{
    private ClientItemId(string value)
    {
        Value = value;
    }

    public string Value { get; }

    public static ClientItemId Create(string value)
    {
        return new ClientItemId(Guard.AgainstNullOrWhiteSpace(value, nameof(value)));
    }

    public override string ToString() => Value;
}
