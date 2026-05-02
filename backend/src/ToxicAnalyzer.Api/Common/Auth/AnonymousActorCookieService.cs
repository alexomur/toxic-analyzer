using Microsoft.AspNetCore.DataProtection;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public interface IAnonymousActorCookieService
{
    string GetOrCreateAnonymousActorId(HttpContext httpContext);
}

public sealed class AnonymousActorCookieService : IAnonymousActorCookieService
{
    private readonly IDataProtector _protector;
    private readonly AuthOptions _options;

    public AnonymousActorCookieService(
        IDataProtectionProvider dataProtectionProvider,
        IOptions<AuthOptions> options)
    {
        _protector = dataProtectionProvider.CreateProtector("ToxicAnalyzer.Api.AnonymousActor");
        _options = options.Value;
    }

    public string GetOrCreateAnonymousActorId(HttpContext httpContext)
    {
        if (httpContext.Request.Cookies.TryGetValue(_options.AnonymousCookieName, out var protectedValue) &&
            TryUnprotectAnonymousId(protectedValue, out var existingId))
        {
            return existingId;
        }

        var newId = Guid.NewGuid().ToString("N");
        httpContext.Response.Cookies.Append(
            _options.AnonymousCookieName,
            _protector.Protect(newId),
            BuildCookieOptions(httpContext));

        return newId;
    }

    private CookieOptions BuildCookieOptions(HttpContext httpContext)
    {
        return new CookieOptions
        {
            HttpOnly = true,
            IsEssential = true,
            SameSite = SameSiteMode.Lax,
            Secure = httpContext.Request.IsHttps
        };
    }

    private bool TryUnprotectAnonymousId(string protectedValue, out string anonymousId)
    {
        try
        {
            anonymousId = _protector.Unprotect(protectedValue);
            return !string.IsNullOrWhiteSpace(anonymousId);
        }
        catch
        {
            anonymousId = string.Empty;
            return false;
        }
    }
}
