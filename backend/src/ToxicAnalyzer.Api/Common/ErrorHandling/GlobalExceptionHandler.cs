using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.Api.Common.ErrorHandling;

public sealed class GlobalExceptionHandler : IExceptionHandler
{
    private readonly IProblemDetailsService _problemDetailsService;
    private readonly IHostEnvironment _environment;
    private readonly ILogger<GlobalExceptionHandler> _logger;

    public GlobalExceptionHandler(
        IProblemDetailsService problemDetailsService,
        IHostEnvironment environment,
        ILogger<GlobalExceptionHandler> logger)
    {
        _problemDetailsService = problemDetailsService;
        _environment = environment;
        _logger = logger;
    }

    public async ValueTask<bool> TryHandleAsync(
        HttpContext httpContext,
        Exception exception,
        CancellationToken cancellationToken)
    {
        var metadata = MapException(exception);

        _logger.LogError(exception, "Request failed with status code {StatusCode}.", metadata.StatusCode);

        var problemDetails = new ProblemDetails
        {
            Status = metadata.StatusCode,
            Title = metadata.Title,
            Detail = ShouldIncludeDetail(exception) ? exception.Message : null,
            Instance = httpContext.Request.Path
        };

        if (metadata.Code is not null)
        {
            problemDetails.Extensions["code"] = metadata.Code;
        }

        if (exception is ValidationException validationException)
        {
            problemDetails.Extensions["errors"] = validationException.Errors
                .Select(error => new { error.Field, error.Message })
                .ToArray();
        }

        if (exception is RateLimitExceededException rateLimitExceededException &&
            rateLimitExceededException.RetryAfter is { } retryAfter &&
            retryAfter > TimeSpan.Zero)
        {
            httpContext.Response.Headers["Retry-After"] =
                Math.Ceiling(retryAfter.TotalSeconds).ToString(System.Globalization.CultureInfo.InvariantCulture);
        }

        httpContext.Response.StatusCode = metadata.StatusCode;

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            ProblemDetails = problemDetails,
            Exception = exception
        });
    }

    private static ProblemDetailsMetadata MapException(Exception exception)
    {
        return exception switch
        {
            ValidationException => new ProblemDetailsMetadata(StatusCodes.Status400BadRequest, "Request validation failed."),
            AuthenticationFailedException => new ProblemDetailsMetadata(StatusCodes.Status401Unauthorized, "Authentication failed."),
            ConflictException conflictException => new ProblemDetailsMetadata(
                StatusCodes.Status409Conflict,
                "Conflict.",
                conflictException.Code),
            RateLimitExceededException => new ProblemDetailsMetadata(StatusCodes.Status429TooManyRequests, "Too many requests."),
            FeatureDisabledException => new ProblemDetailsMetadata(StatusCodes.Status503ServiceUnavailable, "Feature is disabled."),
            NotFoundException => new ProblemDetailsMetadata(StatusCodes.Status404NotFound, "Resource not found."),
            ModelServiceException { FailureKind: ModelServiceFailureKind.Timeout } =>
                new ProblemDetailsMetadata(StatusCodes.Status504GatewayTimeout, "Model service timeout."),
            ModelServiceException => new ProblemDetailsMetadata(StatusCodes.Status503ServiceUnavailable, "Model service unavailable."),
            _ => new ProblemDetailsMetadata(StatusCodes.Status500InternalServerError, "Internal server error.")
        };
    }

    private bool ShouldIncludeDetail(Exception exception)
    {
        return exception is ValidationException
            or AuthenticationFailedException
            or ConflictException
            or RateLimitExceededException
            or FeatureDisabledException
            or NotFoundException
            or ModelServiceException
            || _environment.IsDevelopment();
    }

    private sealed record ProblemDetailsMetadata(int StatusCode, string Title, string? Code = null);
}
