using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Api.Common.Auth;

public sealed class BearerTokenAuthenticationHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    public const string SchemeName = "Bearer";

    private readonly AuthOptions _authOptions;

    public BearerTokenAuthenticationHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder,
        IOptions<AuthOptions> authOptions)
        : base(options, logger, encoder)
    {
        _authOptions = authOptions.Value;
    }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        var headerValue = Request.Headers.Authorization.ToString();

        if (string.IsNullOrWhiteSpace(headerValue) ||
            !headerValue.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        var token = headerValue["Bearer ".Length..].Trim();

        if (string.IsNullOrWhiteSpace(token))
        {
            return Task.FromResult(AuthenticateResult.Fail("Missing bearer token."));
        }

        try
        {
            var tokenHandler = new JwtSecurityTokenHandler();
            var principal = tokenHandler.ValidateToken(token, BuildValidationParameters(), out _);
            var identity = principal.Identity as ClaimsIdentity;

            if (identity is not null && !identity.HasClaim(claim => claim.Type == AuthClaimTypes.AuthScheme))
            {
                identity.AddClaim(new Claim(AuthClaimTypes.AuthScheme, AuthConstants.BearerScheme));
            }

            var ticket = new AuthenticationTicket(principal, SchemeName);
            return Task.FromResult(AuthenticateResult.Success(ticket));
        }
        catch (Exception exception)
        {
            return Task.FromResult(AuthenticateResult.Fail(exception));
        }
    }

    private TokenValidationParameters BuildValidationParameters()
    {
        return new TokenValidationParameters
        {
            ValidateIssuer = _authOptions.Enabled,
            ValidIssuer = _authOptions.Issuer,
            ValidateAudience = _authOptions.Enabled,
            ValidAudience = _authOptions.Audience,
            ValidateIssuerSigningKey = _authOptions.Enabled,
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_authOptions.SigningKey)),
            ValidateLifetime = _authOptions.Enabled,
            ClockSkew = TimeSpan.FromMinutes(1),
            NameClaimType = ClaimTypes.NameIdentifier,
            RoleClaimType = ClaimTypes.Role
        };
    }
}
