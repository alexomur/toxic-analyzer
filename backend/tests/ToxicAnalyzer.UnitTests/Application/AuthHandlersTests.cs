using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Auth.IssueServiceToken;
using ToxicAnalyzer.Application.Auth.Login;
using ToxicAnalyzer.Application.Auth.Register;
using ToxicAnalyzer.Application.Common;

namespace ToxicAnalyzer.UnitTests.Application;

public sealed class AuthHandlersTests
{
    [Fact]
    public async Task RegisterUser_CreatesBrowserSessionWithMemberCapabilities()
    {
        var store = new FakeAuthStore();
        var handler = new RegisterUserHandler(
            store,
            new FakePasswordHasher(),
            new FakeSessionTokenService(),
            new FakeClock(new DateTimeOffset(2026, 5, 3, 9, 0, 0, TimeSpan.Zero)),
            new AuthOptions());

        var result = await handler.HandleAsync(
            new RegisterUserCommand("user@example.com", "strong-password", "tester"),
            CancellationToken.None);

        Assert.Equal("user@example.com", result.User.Email);
        Assert.Equal(["analysis.read", "analysis.vote"], result.Capabilities);
        Assert.Equal("session-token", result.Session.SessionToken);
        Assert.Equal("session-token", result.Session.CsrfToken);
    }

    [Fact]
    public async Task LoginUser_RejectsInvalidCredentials()
    {
        var store = new FakeAuthStore();
        var hasher = new FakePasswordHasher();
        await store.CreateUserAsync("user@example.com", null, hasher.HashPassword("valid-password"), "member", CancellationToken.None);
        var handler = new LoginUserHandler(
            store,
            hasher,
            new FakeSessionTokenService(),
            new FakeClock(new DateTimeOffset(2026, 5, 3, 9, 0, 0, TimeSpan.Zero)),
            new AuthOptions());

        var exception = await Assert.ThrowsAsync<AuthenticationFailedException>(() => handler.HandleAsync(
            new LoginUserCommand("user@example.com", "wrong-password"),
            CancellationToken.None));

        Assert.Equal("Invalid email or password.", exception.Message);
    }

    [Fact]
    public async Task IssueServiceToken_ReturnsCapabilityBoundToken()
    {
        var store = new FakeAuthStore();
        store.ServiceClient = new ServiceClientAuthenticationInfo(
            new AuthServiceClient(Guid.NewGuid(), "discord-bot", "Discord Bot", true, "active", null, DateTimeOffset.UtcNow, DateTimeOffset.UtcNow),
            [new AuthClientSecret(Guid.NewGuid(), "hashed:secret", DateTimeOffset.UtcNow, null, null)],
            [AuthCapabilities.AnalysisRead, AuthCapabilities.AdminUsersManage]);
        var handler = new IssueServiceTokenHandler(
            store,
            new FakePasswordHasher(),
            new FakeAccessTokenIssuer(),
            new FakeClock(new DateTimeOffset(2026, 5, 3, 9, 0, 0, TimeSpan.Zero)),
            new AuthOptions { ServiceAccessTokenLifetime = TimeSpan.FromMinutes(10) });

        var result = await handler.HandleAsync(
            new IssueServiceTokenCommand("discord-bot", "secret"),
            CancellationToken.None);

        Assert.Equal("issued-token", result.AccessToken);
        Assert.Contains(AuthCapabilities.AdminUsersManage, result.Capabilities);
        Assert.True(result.IsTrusted);
    }

    private sealed class FakeAuthStore : IAuthStore
    {
        private readonly Dictionary<string, AuthUser> _users = new(StringComparer.OrdinalIgnoreCase);

        public ServiceClientAuthenticationInfo? ServiceClient { get; set; }

        public Task<AuthUser?> GetUserByEmailAsync(string email, CancellationToken cancellationToken)
        {
            _users.TryGetValue(email, out var user);
            return Task.FromResult(user);
        }

        public Task<AuthUser?> GetUserByIdAsync(Guid userId, CancellationToken cancellationToken)
        {
            return Task.FromResult(_users.Values.SingleOrDefault(user => user.Id == userId));
        }

        public Task<AuthUser> CreateUserAsync(string email, string? username, string passwordHash, string role, CancellationToken cancellationToken)
        {
            var user = new AuthUser(Guid.NewGuid(), email, username, role, passwordHash, "active", DateTimeOffset.UtcNow, DateTimeOffset.UtcNow);
            _users[email] = user;
            return Task.FromResult(user);
        }

        public Task<SessionIssueResult> CreateSessionAsync(
            Guid userId,
            string sessionTokenHash,
            string csrfTokenHash,
            DateTimeOffset createdAt,
            DateTimeOffset expiresAt,
            CancellationToken cancellationToken)
        {
            return Task.FromResult(new SessionIssueResult("session-id", "session-token", "session-token", expiresAt));
        }

        public Task<AuthenticatedSession?> GetAuthenticatedSessionAsync(string sessionTokenHash, DateTimeOffset now, CancellationToken cancellationToken)
        {
            throw new NotSupportedException();
        }

        public Task<bool> ValidateCsrfAsync(string sessionId, string csrfTokenHash, CancellationToken cancellationToken)
        {
            throw new NotSupportedException();
        }

        public Task RevokeSessionAsync(string sessionId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
        {
            return Task.CompletedTask;
        }

        public Task EnsureDevelopmentAdminAsync(string email, string passwordHash, DateTimeOffset now, CancellationToken cancellationToken)
        {
            return Task.CompletedTask;
        }

        public Task<ServiceClientAuthenticationInfo?> GetServiceClientAuthenticationInfoAsync(
            string clientId,
            DateTimeOffset now,
            CancellationToken cancellationToken)
        {
            return Task.FromResult(ServiceClient?.Client.ClientId == clientId ? ServiceClient : null);
        }
    }

    private sealed class FakePasswordHasher : IPasswordHasher
    {
        public string HashPassword(string value) => $"hashed:{value}";

        public bool VerifyPassword(string value, string passwordHash) => HashPassword(value) == passwordHash;
    }

    private sealed class FakeSessionTokenService : ISessionTokenService
    {
        public string GenerateToken() => "session-token";

        public string ComputeHash(string value) => $"hash:{value}";
    }

    private sealed class FakeAccessTokenIssuer : IAccessTokenIssuer
    {
        public ServiceAccessTokenResult IssueServiceAccessToken(
            AuthServiceClient client,
            IReadOnlyList<string> capabilities,
            DateTimeOffset issuedAt,
            DateTimeOffset expiresAt)
        {
            return new ServiceAccessTokenResult(
                "issued-token",
                "Bearer",
                expiresAt,
                $"service:{client.ClientId}",
                client.ClientId,
                client.IsTrusted,
                capabilities);
        }
    }
}
