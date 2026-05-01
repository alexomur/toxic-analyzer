namespace ToxicAnalyzer.Application.Common;

public sealed class NotFoundException : ApplicationException
{
    public NotFoundException(string message)
        : base(message)
    {
    }
}
