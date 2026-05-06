namespace ToxicAnalyzer.Application.Common;

public sealed class RateLimitExceededException : ApplicationException
{
    public RateLimitExceededException(string message, TimeSpan? retryAfter = null)
        : base(message)
    {
        RetryAfter = retryAfter;
    }

    public TimeSpan? RetryAfter { get; }
}
