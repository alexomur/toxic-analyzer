using System.Text.Json;

namespace ToxicAnalyzer.Api.Common.Security;

public sealed class RequestBodySizeLimitMiddleware
{
    public const long MaxRequestBodyBytes = 1_048_576;

    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    private readonly RequestDelegate _next;

    public RequestBodySizeLimitMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext httpContext)
    {
        if (httpContext.Request.ContentLength is > MaxRequestBodyBytes)
        {
            httpContext.Response.StatusCode = StatusCodes.Status413PayloadTooLarge;
            httpContext.Response.ContentType = "application/problem+json";
            await JsonSerializer.SerializeAsync(
                httpContext.Response.Body,
                new
                {
                    title = "Payload too large.",
                    status = StatusCodes.Status413PayloadTooLarge,
                    detail = $"Request body must not exceed {MaxRequestBodyBytes} bytes.",
                    instance = httpContext.Request.Path.Value
                },
                SerializerOptions);
            return;
        }

        await _next(httpContext);
    }
}
