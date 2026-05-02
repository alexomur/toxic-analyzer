namespace ToxicAnalyzer.Application.Common;

public sealed class AuthenticationFailedException : ApplicationException
{
    public AuthenticationFailedException(string message)
        : base(message)
    {
    }
}
