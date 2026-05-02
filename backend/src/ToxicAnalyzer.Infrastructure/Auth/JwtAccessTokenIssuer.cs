using System.IdentityModel.Tokens.Jwt;
using System.Security.Claims;
using System.Text;

using Microsoft.Extensions.Options;
using Microsoft.IdentityModel.Tokens;

using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class JwtAccessTokenIssuer : IAccessTokenIssuer
{
    private readonly AuthOptions _authOptions;

    public JwtAccessTokenIssuer(IOptions<AuthOptions> authOptions)
    {
        _authOptions = authOptions.Value;
    }

    public ServiceAccessTokenResult IssueServiceAccessToken(
        AuthServiceClient client,
        IReadOnlyList<string> capabilities,
        DateTimeOffset issuedAt,
        DateTimeOffset expiresAt)
    {
        var subjectId = $"service:{client.ClientId}";
        var claims = new List<Claim>
        {
            new(JwtRegisteredClaimNames.Sub, subjectId),
            new(ClaimTypes.NameIdentifier, subjectId),
            new(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString("N")),
            new(AuthClaimTypes.ActorType, "service"),
            new(AuthClaimTypes.ClientId, client.ClientId),
            new(AuthClaimTypes.AuthScheme, "Bearer"),
            new(ClaimTypes.Name, client.DisplayName)
        };

        if (!string.IsNullOrWhiteSpace(client.TenantId))
        {
            claims.Add(new Claim(AuthClaimTypes.TenantId, client.TenantId));
        }

        if (client.IsTrusted)
        {
            claims.Add(new Claim(ClaimTypes.Role, _authOptions.TrustedServiceRole));
        }

        var resolvedCapabilities = capabilities.Distinct(StringComparer.Ordinal).Order(StringComparer.Ordinal).ToArray();

        foreach (var capability in resolvedCapabilities)
        {
            claims.Add(new Claim(AuthClaimTypes.Capability, capability));
        }

        if (resolvedCapabilities.Length > 0)
        {
            claims.Add(new Claim(AuthClaimTypes.Scope, string.Join(' ', resolvedCapabilities)));
        }

        var credentials = new SigningCredentials(
            new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_authOptions.SigningKey)),
            SecurityAlgorithms.HmacSha256);

        var token = new JwtSecurityToken(
            issuer: _authOptions.Issuer,
            audience: _authOptions.Audience,
            claims: claims,
            notBefore: issuedAt.UtcDateTime,
            expires: expiresAt.UtcDateTime,
            signingCredentials: credentials);

        return new ServiceAccessTokenResult(
            new JwtSecurityTokenHandler().WriteToken(token),
            "Bearer",
            expiresAt,
            subjectId,
            client.ClientId,
            client.IsTrusted,
            resolvedCapabilities);
    }
}
