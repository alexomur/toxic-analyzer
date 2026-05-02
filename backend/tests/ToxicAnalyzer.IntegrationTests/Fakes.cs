using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;
using ToxicAnalyzer.Infrastructure.ModelService;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Infrastructure.Auth;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class FakeModelPredictionClient : IModelPredictionClient
{
    public ModelPrediction SinglePrediction { get; set; } = CreatePrediction(0, 0.12m);

    public ExplainedModelPrediction ExplainedPrediction { get; set; } = CreateExplainedPrediction(0, 0.12m);

    public IReadOnlyList<ModelPrediction> BatchPredictions { get; set; } = [];

    public Exception? ExceptionToThrow { get; set; }

    public int PredictAsyncCallCount { get; private set; }

    public int PredictWithExplanationAsyncCallCount { get; private set; }

    public void Reset()
    {
        SinglePrediction = CreatePrediction(0, 0.12m);
        ExplainedPrediction = CreateExplainedPrediction(0, 0.12m);
        BatchPredictions = [];
        ExceptionToThrow = null;
        PredictAsyncCallCount = 0;
        PredictWithExplanationAsyncCallCount = 0;
    }

    public Task<ModelPrediction> PredictAsync(TextContent text, CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        PredictAsyncCallCount++;
        return Task.FromResult(SinglePrediction);
    }

    public Task<ExplainedModelPrediction> PredictWithExplanationAsync(
        TextContent text,
        CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        PredictWithExplanationAsyncCallCount++;
        return Task.FromResult(ExplainedPrediction);
    }

    public Task<IReadOnlyList<ModelPrediction>> PredictBatchAsync(
        IReadOnlyList<TextContent> texts,
        CancellationToken cancellationToken)
    {
        if (ExceptionToThrow is not null)
        {
            throw ExceptionToThrow;
        }

        return Task.FromResult(BatchPredictions);
    }

    public static ModelPrediction CreatePrediction(int label, decimal toxicProbability)
    {
        return new ModelPrediction(
            PredictionLabel.FromInt(label),
            new ToxicProbability(toxicProbability),
            ModelIdentity.Create("baseline", "v3.3"));
    }

    public static ExplainedModelPrediction CreateExplainedPrediction(int label, decimal toxicProbability)
    {
        return new ExplainedModelPrediction(
            CreatePrediction(label, toxicProbability),
            new ModelPredictionExplanation(
                0.89m,
                toxicProbability,
                0.80m,
                [new ModelPredictionFeature("some feature", 0.42m)]));
    }
}

public sealed class FakeClock : IClock
{
    public FakeClock(DateTimeOffset utcNow)
    {
        UtcNow = utcNow;
    }

    public DateTimeOffset UtcNow { get; }
}

public sealed class FakeAnalysisTextVotingRepository : IAnalysisTextVotingRepository
{
    public AnalysisTextVotingCandidate? RandomCandidate { get; set; }

    public AnalysisTextVotingDetails? Details { get; set; }

    public bool RegisterVoteResult { get; set; } = true;

    public List<(Guid Id, AnalysisTextVoteKind Vote, CurrentActor Actor)> RegisteredVotes { get; } = [];

    public void Reset()
    {
        RandomCandidate = null;
        Details = null;
        RegisterVoteResult = true;
        RegisteredVotes.Clear();
    }

    public Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken)
    {
        return Task.FromResult(RandomCandidate);
    }

    public Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
    {
        return Task.FromResult(Details);
    }

    public Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CurrentActor actor, CancellationToken cancellationToken)
    {
        RegisteredVotes.Add((id, vote, actor));
        return Task.FromResult(RegisterVoteResult);
    }
}

public sealed class FakeAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public List<(ToxicityAnalysis Analysis, CurrentActor Actor)> CapturedAnalyses { get; } = [];

    public void Reset()
    {
        CapturedAnalyses.Clear();
    }

    public void Schedule(ToxicityAnalysis analysis, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        ArgumentNullException.ThrowIfNull(actor);
        CapturedAnalyses.Add((analysis, actor));
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        ArgumentNullException.ThrowIfNull(actor);
        CapturedAnalyses.AddRange(analyses.Select(analysis => (analysis, actor)));
    }
}

public sealed class FakeAuthStore : IAuthStore
{
    private readonly Dictionary<string, AuthUser> _usersByEmail = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<Guid, AuthUser> _usersById = [];
    private readonly Dictionary<string, FakeSessionRecord> _sessionsById = [];
    private readonly Dictionary<string, FakeSessionRecord> _sessionsByTokenHash = [];
    private readonly Dictionary<Guid, HashSet<string>> _userCapabilities = [];
    private readonly Dictionary<string, ServiceClientAuthenticationInfo> _serviceClients = new(StringComparer.OrdinalIgnoreCase);
    private readonly PasswordHasher _passwordHasher = new();

    public void Reset()
    {
        _usersByEmail.Clear();
        _usersById.Clear();
        _sessionsById.Clear();
        _sessionsByTokenHash.Clear();
        _userCapabilities.Clear();
        _serviceClients.Clear();
    }

    public Task<AuthUser?> GetUserByEmailAsync(string email, CancellationToken cancellationToken)
    {
        _usersByEmail.TryGetValue(email, out var user);
        return Task.FromResult(user);
    }

    public Task<AuthUser?> GetUserByIdAsync(Guid userId, CancellationToken cancellationToken)
    {
        _usersById.TryGetValue(userId, out var user);
        return Task.FromResult(user);
    }

    public Task<AuthUser> CreateUserAsync(string email, string? username, string passwordHash, string role, CancellationToken cancellationToken)
    {
        var now = DateTimeOffset.UtcNow;
        var user = new AuthUser(Guid.NewGuid(), email, username, role, passwordHash, "active", now, now);
        _usersByEmail[email] = user;
        _usersById[user.Id] = user;
        _userCapabilities[user.Id] = ResolveRoleCapabilities(role);
        return Task.FromResult(user);
    }

    public Task<SessionIssueResult> CreateSessionAsync(Guid userId, string sessionTokenHash, string csrfTokenHash, DateTimeOffset createdAt, DateTimeOffset expiresAt, CancellationToken cancellationToken)
    {
        var sessionId = Guid.NewGuid().ToString("N");
        var record = new FakeSessionRecord(sessionId, userId, sessionTokenHash, csrfTokenHash, createdAt, createdAt, expiresAt, null);
        _sessionsById[sessionId] = record;
        _sessionsByTokenHash[sessionTokenHash] = record;
        return Task.FromResult(new SessionIssueResult(sessionId, string.Empty, string.Empty, expiresAt));
    }

    public Task<AuthenticatedSession?> GetAuthenticatedSessionAsync(string sessionTokenHash, DateTimeOffset now, CancellationToken cancellationToken)
    {
        if (!_sessionsByTokenHash.TryGetValue(sessionTokenHash, out var record) ||
            record.RevokedAt is not null ||
            record.ExpiresAt <= now ||
            !_usersById.TryGetValue(record.UserId, out var user))
        {
            return Task.FromResult<AuthenticatedSession?>(null);
        }

        var updated = record with { LastSeenAt = now };
        _sessionsById[record.SessionId] = updated;
        _sessionsByTokenHash[sessionTokenHash] = updated;

        return Task.FromResult<AuthenticatedSession?>(new AuthenticatedSession(
            updated.SessionId,
            user,
            updated.ExpiresAt,
            updated.LastSeenAt,
            ResolveCapabilities(user)));
    }

    public Task<bool> ValidateCsrfAsync(string sessionId, string csrfTokenHash, CancellationToken cancellationToken)
    {
        var valid = _sessionsById.TryGetValue(sessionId, out var record) &&
                    record.RevokedAt is null &&
                    string.Equals(record.CsrfTokenHash, csrfTokenHash, StringComparison.Ordinal);
        return Task.FromResult(valid);
    }

    public Task RevokeSessionAsync(string sessionId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        if (_sessionsById.TryGetValue(sessionId, out var record))
        {
            var revoked = record with { RevokedAt = revokedAt };
            _sessionsById[sessionId] = revoked;
            _sessionsByTokenHash[record.SessionTokenHash] = revoked;
        }

        return Task.CompletedTask;
    }

    public Task EnsureDevelopmentAdminAsync(string email, string passwordHash, DateTimeOffset now, CancellationToken cancellationToken)
    {
        if (_usersByEmail.ContainsKey(email))
        {
            return Task.CompletedTask;
        }

        var user = new AuthUser(Guid.NewGuid(), email, null, "admin", passwordHash, "active", now, now);
        _usersByEmail[email] = user;
        _usersById[user.Id] = user;
        _userCapabilities[user.Id] = ResolveRoleCapabilities(user.Role);
        return Task.CompletedTask;
    }

    public Task<ServiceClientAuthenticationInfo?> GetServiceClientAuthenticationInfoAsync(
        string clientId,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        _serviceClients.TryGetValue(clientId, out var serviceClient);
        return Task.FromResult(serviceClient);
    }

    public void AddServiceClient(
        string clientId,
        string clientSecret,
        bool isTrusted,
        params string[] capabilities)
    {
        var now = DateTimeOffset.UtcNow;
        var client = new AuthServiceClient(
            Guid.NewGuid(),
            clientId,
            clientId,
            isTrusted,
            "active",
            null,
            now,
            now);
        var secret = new AuthClientSecret(Guid.NewGuid(), _passwordHasher.HashPassword(clientSecret), now, null, null);
        _serviceClients[clientId] = new ServiceClientAuthenticationInfo(
            client,
            [secret],
            capabilities.Distinct(StringComparer.Ordinal).ToArray());
    }

    private IReadOnlyList<string> ResolveCapabilities(AuthUser user)
    {
        return _userCapabilities.TryGetValue(user.Id, out var capabilities)
            ? capabilities.OrderBy(value => value, StringComparer.Ordinal).ToArray()
            : ResolveRoleCapabilities(user.Role).OrderBy(value => value, StringComparer.Ordinal).ToArray();
    }

    private static HashSet<string> ResolveRoleCapabilities(string role)
    {
        return role switch
        {
            "admin" =>
            [
                AuthCapabilities.AnalysisRead,
                AuthCapabilities.AnalysisVote,
                AuthCapabilities.ModelReload,
                AuthCapabilities.ModelRetrain,
                AuthCapabilities.DatasetUpdate,
                AuthCapabilities.AdminUsersManage
            ],
            _ =>
            [
                AuthCapabilities.AnalysisRead,
                AuthCapabilities.AnalysisVote
            ]
        };
    }

    private sealed record FakeSessionRecord(
        string SessionId,
        Guid UserId,
        string SessionTokenHash,
        string CsrfTokenHash,
        DateTimeOffset CreatedAt,
        DateTimeOffset LastSeenAt,
        DateTimeOffset ExpiresAt,
        DateTimeOffset? RevokedAt);
}
