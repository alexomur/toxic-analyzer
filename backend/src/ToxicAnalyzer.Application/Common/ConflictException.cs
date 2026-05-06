namespace ToxicAnalyzer.Application.Common;

public sealed class ConflictException : ApplicationException
{
    public ConflictException(string message, string? code = null)
        : base(message)
    {
        Code = code;
    }

    public string? Code { get; }
}
