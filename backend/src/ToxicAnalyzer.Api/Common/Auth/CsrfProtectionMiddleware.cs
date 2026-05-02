using Microsoft.AspNetCore.Http.Extensions;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public sealed class CsrfProtectionMiddleware
{
    private readonly RequestDelegate _next;

    public CsrfProtectionMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context, IAuthStore authStore, ISessionTokenService sessionTokenService)
    {
        if (!RequiresCsrfValidation(context))
        {
            await _next(context);
            return;
        }

        if (!context.Request.Headers.TryGetValue(AuthConstants.CsrfHeaderName, out var csrfHeader) ||
            string.IsNullOrWhiteSpace(csrfHeader))
        {
            context.Response.StatusCode = StatusCodes.Status400BadRequest;
            await context.Response.WriteAsJsonAsync(new
            {
                title = "CSRF token validation failed.",
                status = 400,
                detail = $"Missing {AuthConstants.CsrfHeaderName} header.",
                instance = context.Request.GetDisplayUrl()
            });
            return;
        }

        var sessionId = context.User.FindFirst(AuthConstants.SessionIdClaimType)?.Value;
        if (string.IsNullOrWhiteSpace(sessionId))
        {
            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
            return;
        }

        var valid = await authStore.ValidateCsrfAsync(
            sessionId,
            sessionTokenService.ComputeHash(csrfHeader!),
            context.RequestAborted);

        if (!valid)
        {
            context.Response.StatusCode = StatusCodes.Status400BadRequest;
            await context.Response.WriteAsJsonAsync(new
            {
                title = "CSRF token validation failed.",
                status = 400,
                detail = "The supplied CSRF token is invalid.",
                instance = context.Request.GetDisplayUrl()
            });
            return;
        }

        await _next(context);
    }

    private static bool RequiresCsrfValidation(HttpContext context)
    {
        if (HttpMethods.IsGet(context.Request.Method) ||
            HttpMethods.IsHead(context.Request.Method) ||
            HttpMethods.IsOptions(context.Request.Method) ||
            HttpMethods.IsTrace(context.Request.Method))
        {
            return false;
        }

        if (context.Request.Path.StartsWithSegments("/api/v1/auth/login") ||
            context.Request.Path.StartsWithSegments("/api/v1/auth/register"))
        {
            return false;
        }

        return context.User.Identity?.IsAuthenticated == true &&
               string.Equals(
                   context.User.FindFirst(AuthClaimTypes.AuthScheme)?.Value,
                   AuthConstants.SessionScheme,
                   StringComparison.Ordinal);
    }
}
