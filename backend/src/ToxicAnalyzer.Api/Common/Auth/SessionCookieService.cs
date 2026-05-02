using Microsoft.Extensions.Options;
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

    public SessionCookieService(IOptions<AuthOptions> options)
    {
        _options = options.Value;
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
        httpContext.Response.Cookies.Delete(_options.SessionCookieName);
        httpContext.Response.Cookies.Delete(_options.CsrfCookieName);
    }

    private CookieOptions CreateCookieOptions(HttpContext httpContext, bool httpOnly, DateTimeOffset expiresAt)
    {
        return new CookieOptions
        {
            HttpOnly = httpOnly,
            IsEssential = true,
            SameSite = SameSiteMode.Lax,
            Secure = httpContext.Request.IsHttps,
            Expires = expiresAt
        };
    }
}
