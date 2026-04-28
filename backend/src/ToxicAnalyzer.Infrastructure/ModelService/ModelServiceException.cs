using System.Net;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceException : ToxicAnalyzer.Application.Common.ApplicationException
{
    public ModelServiceException(string message)
        : base(message)
    {
    }

    public ModelServiceException(string message, Exception innerException)
        : base(message, innerException)
    {
    }

    public HttpStatusCode? StatusCode { get; init; }

    public ModelServiceFailureKind FailureKind { get; init; } = ModelServiceFailureKind.Unavailable;
}
