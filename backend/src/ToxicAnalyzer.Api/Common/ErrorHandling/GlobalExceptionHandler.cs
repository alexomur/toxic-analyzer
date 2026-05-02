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
        var (statusCode, title) = MapException(exception);

        _logger.LogError(exception, "Request failed with status code {StatusCode}.", statusCode);

        var problemDetails = new ProblemDetails
        {
            Status = statusCode,
            Title = title,
            Detail = ShouldIncludeDetail(exception) ? exception.Message : null,
            Instance = httpContext.Request.Path
        };

        if (exception is ValidationException validationException)
        {
            problemDetails.Extensions["errors"] = validationException.Errors
                .Select(error => new { error.Field, error.Message })
                .ToArray();
        }

        httpContext.Response.StatusCode = statusCode;

        return await _problemDetailsService.TryWriteAsync(new ProblemDetailsContext
        {
            HttpContext = httpContext,
            ProblemDetails = problemDetails,
            Exception = exception
        });
    }

    private static (int StatusCode, string Title) MapException(Exception exception)
    {
        return exception switch
        {
            ValidationException => (StatusCodes.Status400BadRequest, "Request validation failed."),
            AuthenticationFailedException => (StatusCodes.Status401Unauthorized, "Authentication failed."),
            ConflictException => (StatusCodes.Status409Conflict, "Conflict."),
            NotFoundException => (StatusCodes.Status404NotFound, "Resource not found."),
            ModelServiceException { FailureKind: ModelServiceFailureKind.Timeout } =>
                (StatusCodes.Status504GatewayTimeout, "Model service timeout."),
            ModelServiceException => (StatusCodes.Status503ServiceUnavailable, "Model service unavailable."),
            _ => (StatusCodes.Status500InternalServerError, "Internal server error.")
        };
    }

    private bool ShouldIncludeDetail(Exception exception)
    {
        return exception is ValidationException || _environment.IsDevelopment();
    }
}
