using Microsoft.Extensions.Options;
using Microsoft.Extensions.Hosting;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public interface ISessionCookieService
{
    void AppendSessionCookies(HttpContext httpContext, SessionIssueResult session);

    void ClearSessionCookies(HttpContext httpContext);
}

public sealed class SessionCookieService : ISessionCookieService
{
    private readonly AuthOptions _options;
    private readonly IHostEnvironment _environment;

    public SessionCookieService(IOptions<AuthOptions> options, IHostEnvironment environment)
    {
        _options = options.Value;
        _environment = environment;
    }

    public void AppendSessionCookies(HttpContext httpContext, SessionIssueResult session)
    {
        httpContext.Response.Cookies.Append(
            _options.SessionCookieName,
            session.SessionToken,
            CreateCookieOptions(httpContext, true, session.ExpiresAt));

        httpContext.Response.Cookies.Append(
            _options.CsrfCookieName,
            session.CsrfToken,
            CreateCookieOptions(httpContext, false, session.ExpiresAt));
    }

    public void ClearSessionCookies(HttpContext httpContext)
    {
        var options = CreateCookieOptions(httpContext, true, DateTimeOffset.UnixEpoch);
        httpContext.Response.Cookies.Delete(_options.SessionCookieName, options);
        httpContext.Response.Cookies.Delete(_options.CsrfCookieName, CreateCookieOptions(httpContext, false, DateTimeOffset.UnixEpoch));
    }

    private CookieOptions CreateCookieOptions(HttpContext httpContext, bool httpOnly, DateTimeOffset expiresAt)
    {
        return new CookieOptions
        {
            HttpOnly = httpOnly,
            IsEssential = true,
            SameSite = SameSiteMode.Lax,
            Secure = !_environment.IsDevelopment() || httpContext.Request.IsHttps,
            Expires = expiresAt
        };
    }
}
