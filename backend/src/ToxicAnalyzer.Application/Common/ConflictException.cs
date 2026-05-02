namespace ToxicAnalyzer.Application.Common;

public sealed class ConflictException : ApplicationException
{
    public ConflictException(string message)
        : base(message)
    {
    }
}
