using System.Security.Cryptography;
using System.Text;

namespace ToxicAnalyzer.Domain.Texts;

public sealed record TextFingerprint
{
    private TextFingerprint(string value)
    {
        Value = value;
    }

    public string Value { get; }

    public static TextFingerprint From(TextContent text)
    {
        ArgumentNullException.ThrowIfNull(text);

        var bytes = Encoding.UTF8.GetBytes(text.Normalized);
        var hash = SHA256.HashData(bytes);
        return new TextFingerprint(Convert.ToHexString(hash).ToLowerInvariant());
    }

    public override string ToString() => Value;
}
