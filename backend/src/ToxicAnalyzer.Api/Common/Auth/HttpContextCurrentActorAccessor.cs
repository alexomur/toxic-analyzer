using System.Security.Claims;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public sealed class HttpContextCurrentActorAccessor : ICurrentActorAccessor
{
    private const string CurrentActorItemKey = "__current_actor";

    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly AuthOptions _options;
    private readonly IAnonymousActorCookieService _anonymousActorCookieService;

    public HttpContextCurrentActorAccessor(
        IHttpContextAccessor httpContextAccessor,
        IAnonymousActorCookieService anonymousActorCookieService,
        IOptions<AuthOptions> options)
    {
        _httpContextAccessor = httpContextAccessor;
        _anonymousActorCookieService = anonymousActorCookieService;
        _options = options.Value;
    }

    public CurrentActor GetCurrent()
    {
        var httpContext = _httpContextAccessor.HttpContext
            ?? throw new InvalidOperationException("The current actor is available only during an HTTP request.");

        if (httpContext.Items.TryGetValue(CurrentActorItemKey, out var cachedActor) &&
            cachedActor is CurrentActor actor)
        {
            return actor;
        }

        actor = ResolveActor(httpContext);
        httpContext.Items[CurrentActorItemKey] = actor;
        return actor;
    }

    private CurrentActor ResolveActor(HttpContext httpContext)
    {
        var principal = httpContext.User;

        if (principal.Identity?.IsAuthenticated == true)
        {
            var subjectId = principal.FindFirstValue(ClaimTypes.NameIdentifier)
                ?? principal.FindFirstValue("sub")
                ?? throw new InvalidOperationException("Authenticated requests must include a subject identifier.");

            var actorType = ResolveActorType(principal);
            var clientId = principal.FindFirstValue(AuthClaimTypes.ClientId);
            var tenantId = principal.FindFirstValue(AuthClaimTypes.TenantId);
            var sessionId = principal.FindFirstValue(AuthConstants.SessionIdClaimType);
            var authScheme = principal.FindFirstValue(AuthClaimTypes.AuthScheme)
                ?? principal.Identity.AuthenticationType
                ?? AuthConstants.BearerScheme;
            var roles = principal.FindAll(ClaimTypes.Role).Select(claim => claim.Value).ToArray();
            var scopes = principal.FindAll(AuthClaimTypes.Scope)
                .SelectMany(claim => claim.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                .Distinct(StringComparer.Ordinal)
                .ToArray();
            var capabilities = principal.FindAll(AuthClaimTypes.Capability)
                .Select(claim => claim.Value)
                .Concat(scopes)
                .Distinct(StringComparer.Ordinal)
                .Order(StringComparer.Ordinal)
                .ToArray();

            return new CurrentActor(true, actorType, subjectId, clientId, tenantId, sessionId, authScheme, roles, scopes, capabilities);
        }

        var anonymousId = _anonymousActorCookieService.GetOrCreateAnonymousActorId(httpContext);
        return CurrentActor.Anonymous(anonymousId);
    }

    private ActorType ResolveActorType(ClaimsPrincipal principal)
    {
        var actorTypeValue = principal.FindFirstValue(AuthClaimTypes.ActorType);

        if (string.Equals(actorTypeValue, "service", StringComparison.OrdinalIgnoreCase))
        {
            return ActorType.Service;
        }

        if (principal.IsInRole(_options.AdminRole))
        {
            return ActorType.Admin;
        }

        return ActorType.User;
    }
}
