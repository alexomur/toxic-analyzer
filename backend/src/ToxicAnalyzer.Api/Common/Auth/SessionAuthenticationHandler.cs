using System.Security.Claims;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public sealed class SessionAuthenticationHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    private readonly IAuthStore _authStore;
    private readonly ISessionTokenService _sessionTokenService;
    private readonly AuthOptions _authOptions;

    public SessionAuthenticationHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder,
        IAuthStore authStore,
        ISessionTokenService sessionTokenService,
        IOptions<AuthOptions> authOptions)
        : base(options, logger, encoder)
    {
        _authStore = authStore;
        _sessionTokenService = sessionTokenService;
        _authOptions = authOptions.Value;
    }

    protected override async Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        if (!Request.Cookies.TryGetValue(_authOptions.SessionCookieName, out var sessionToken) ||
            string.IsNullOrWhiteSpace(sessionToken))
        {
            return AuthenticateResult.NoResult();
        }

        var session = await _authStore.GetAuthenticatedSessionAsync(
            _sessionTokenService.ComputeHash(sessionToken),
            DateTimeOffset.UtcNow,
            Context.RequestAborted);

        if (session is null)
        {
            return AuthenticateResult.Fail("Invalid or expired session.");
        }

        var actorType = string.Equals(session.User.Role, _authOptions.AdminRole, StringComparison.OrdinalIgnoreCase)
            ? "admin"
            : "user";

        var claims = new List<Claim>
        {
            new(ClaimTypes.NameIdentifier, session.User.Id.ToString()),
            new(ClaimTypes.Email, session.User.Email),
            new(ClaimTypes.Role, session.User.Role),
            new(AuthClaimTypes.ActorType, actorType),
            new(AuthConstants.SessionIdClaimType, session.SessionId),
            new(AuthClaimTypes.AuthScheme, AuthConstants.SessionScheme)
        };

        if (!string.IsNullOrWhiteSpace(session.User.Username))
        {
            claims.Add(new Claim(ClaimTypes.Name, session.User.Username));
        }

        foreach (var capability in session.Capabilities)
        {
            claims.Add(new Claim(AuthClaimTypes.Capability, capability));
        }

        if (session.Capabilities.Count > 0)
        {
            claims.Add(new Claim(AuthClaimTypes.Scope, string.Join(' ', session.Capabilities)));
        }

        var identity = new ClaimsIdentity(claims, AuthConstants.SessionScheme);
        var principal = new ClaimsPrincipal(identity);
        return AuthenticateResult.Success(new AuthenticationTicket(principal, AuthConstants.SessionScheme));
    }
}
