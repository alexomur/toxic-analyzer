namespace ToxicAnalyzer.Application.Common;

public sealed class FeatureDisabledException : ApplicationException
{
    public FeatureDisabledException(string message)
        : base(message)
    {
    }
}
