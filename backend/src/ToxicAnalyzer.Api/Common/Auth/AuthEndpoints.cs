using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.Extensions.Options;
using ToxicAnalyzer.Api.Common.Auth;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Auth.IssueServiceToken;
using ToxicAnalyzer.Application.Auth.Login;
using ToxicAnalyzer.Application.Auth.Logout;
using ToxicAnalyzer.Application.Auth.Register;

namespace ToxicAnalyzer.Api.Endpoints;

public static class AuthEndpoints
{
    public static IEndpointRouteBuilder MapAuthEndpoints(this IEndpointRouteBuilder endpoints)
    {
        var group = endpoints.MapGroup("/api/v1/auth")
            .WithTags("Auth");

        group.MapPost("/register", RegisterAsync)
            .WithName("RegisterUser")
            .WithSummary("Register a new frontend user and create a browser session.")
            .Produces<AuthSessionResponse>(StatusCodes.Status201Created)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status409Conflict);

        group.MapPost("/login", LoginAsync)
            .WithName("LoginUser")
            .WithSummary("Authenticate a frontend user and create a browser session.")
            .Produces<AuthSessionResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status401Unauthorized);

        group.MapPost("/service-token", IssueServiceTokenAsync)
            .AllowAnonymous()
            .WithName("IssueServiceToken")
            .WithSummary("Authenticate a service client and issue a short-lived bearer access token.")
            .Produces<ServiceTokenResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status400BadRequest)
            .ProducesProblem(StatusCodes.Status401Unauthorized);

        group.MapPost("/logout", LogoutAsync)
            .WithName("LogoutUser")
            .WithSummary("Revoke the current browser session.")
            .RequireAuthorization(AuthPolicies.RequireAuthenticated)
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status401Unauthorized)
            .ProducesProblem(StatusCodes.Status400BadRequest);

        group.MapGet("/me", GetCurrentActor)
            .WithName("GetCurrentActor")
            .WithSummary("Get the authenticated actor context and browser CSRF token when session auth is active.")
            .RequireAuthorization(AuthPolicies.RequireAuthenticated)
            .Produces<AuthActorResponse>(StatusCodes.Status200OK)
            .ProducesProblem(StatusCodes.Status401Unauthorized);

        group.MapGet("/admin-access", () => Results.NoContent())
            .WithName("CheckAdminAccess")
            .WithSummary("Check whether the current actor has the admin.users.manage capability.")
            .RequireAuthorization(AuthPolicies.Capability(AuthCapabilities.AdminUsersManage))
            .Produces(StatusCodes.Status204NoContent)
            .ProducesProblem(StatusCodes.Status401Unauthorized)
            .ProducesProblem(StatusCodes.Status403Forbidden);

        return endpoints;
    }

    private static async Task<IResult> RegisterAsync(
        RegisterRequest request,
        HttpContext httpContext,
        RegisterUserHandler handler,
        ISessionCookieService sessionCookieService,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(
            new RegisterUserCommand(request.Email, request.Password, request.Username),
            cancellationToken);
        sessionCookieService.AppendSessionCookies(httpContext, result.Session);

        return Results.Created("/api/v1/auth/me", ToSessionResponse(result));
    }

    private static async Task<IResult> LoginAsync(
        LoginRequest request,
        HttpContext httpContext,
        LoginUserHandler handler,
        ISessionCookieService sessionCookieService,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(
            new LoginUserCommand(request.Email, request.Password),
            cancellationToken);
        sessionCookieService.AppendSessionCookies(httpContext, result.Session);
        return Results.Ok(ToSessionResponse(result));
    }

    private static async Task<IResult> IssueServiceTokenAsync(
        ServiceTokenRequest request,
        IssueServiceTokenHandler handler,
        CancellationToken cancellationToken)
    {
        var result = await handler.HandleAsync(
            new IssueServiceTokenCommand(request.ClientId, request.ClientSecret),
            cancellationToken);
        return Results.Ok(new ServiceTokenResponse(
            result.TokenType,
            result.AccessToken,
            result.ExpiresAt,
            result.SubjectId,
            result.ClientId,
            result.IsTrusted,
            result.Capabilities.ToArray()));
    }

    private static async Task<IResult> LogoutAsync(
        HttpContext httpContext,
        ClaimsPrincipal user,
        LogoutSessionHandler handler,
        ISessionCookieService sessionCookieService,
        CancellationToken cancellationToken)
    {
        var sessionId = user.FindFirstValue(AuthConstants.SessionIdClaimType);
        await handler.HandleAsync(new LogoutSessionCommand(sessionId ?? string.Empty), cancellationToken);

        sessionCookieService.ClearSessionCookies(httpContext);
        return Results.NoContent();
    }

    private static IResult GetCurrentActor(HttpContext httpContext, ClaimsPrincipal user, IOptions<AuthOptions> authOptions)
    {
        return Results.Ok(ToActorResponse(httpContext, user, authOptions.Value));
    }

    private static AuthSessionResponse ToSessionResponse(BrowserSessionResult result)
    {
        return new AuthSessionResponse(
            string.Equals(result.User.Role, "admin", StringComparison.OrdinalIgnoreCase) ? "admin" : "user",
            result.User.Email,
            result.User.Username,
            result.Session.CsrfToken,
            result.Session.ExpiresAt,
            result.Capabilities.ToArray());
    }

    private static AuthActorResponse ToActorResponse(HttpContext httpContext, ClaimsPrincipal user, AuthOptions authOptions)
    {
        var authScheme = user.FindFirstValue(AuthClaimTypes.AuthScheme)
            ?? user.Identity?.AuthenticationType
            ?? AuthConstants.BearerScheme;
        var csrfToken = string.Equals(authScheme, AuthConstants.SessionScheme, StringComparison.Ordinal)
            && httpContext.Request.Cookies.TryGetValue(authOptions.CsrfCookieName, out var csrfCookie)
            ? csrfCookie
            : null;

        return new AuthActorResponse(
            user.FindFirstValue(AuthClaimTypes.ActorType)
                ?? (user.IsInRole("admin") ? "admin" : "user"),
            user.FindFirstValue(ClaimTypes.NameIdentifier) ?? user.FindFirstValue("sub") ?? string.Empty,
            user.FindFirstValue(AuthClaimTypes.ClientId),
            user.FindFirstValue(AuthClaimTypes.TenantId),
            user.FindFirstValue(AuthConstants.SessionIdClaimType),
            authScheme,
            user.FindFirstValue(ClaimTypes.Email),
            user.FindFirstValue(ClaimTypes.Name),
            csrfToken,
            user.FindAll(ClaimTypes.Role).Select(claim => claim.Value).ToArray(),
            user.FindAll(AuthClaimTypes.Capability)
                .Select(claim => claim.Value)
                .Concat(user.FindAll(AuthClaimTypes.Scope)
                    .SelectMany(claim => claim.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries)))
                .Distinct(StringComparer.Ordinal)
                .ToArray(),
            user.FindAll(AuthClaimTypes.Scope)
                .SelectMany(claim => claim.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries))
                .Distinct(StringComparer.Ordinal)
                .ToArray());
    }
}
