namespace ToxicAnalyzer.Application.Common;

public sealed class ValidationException : ApplicationException
{
    public ValidationException(string message)
        : base(message)
    {
        Errors = [];
    }

    public ValidationException(string message, IReadOnlyList<ValidationError> errors)
        : base(message)
    {
        Errors = errors;
    }

    public IReadOnlyList<ValidationError> Errors { get; }
}
