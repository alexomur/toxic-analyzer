using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Application.Toxicity.AnalyzeBatch;
using ToxicAnalyzer.Application.Toxicity.AnalyzeText;
using ToxicAnalyzer.Application.Toxicity.GetRandomText;
using ToxicAnalyzer.Application.Toxicity.GetTextById;
using ToxicAnalyzer.Application.Toxicity.VoteText;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.UnitTests.Application;

internal sealed class TestFixture
{
    private TestFixture(
        FakeModelPredictionClient modelClient,
        FakeAnalysisCaptureScheduler analysisCaptureScheduler,
        FakeClock clock,
        FakeAnalysisTextVotingRepository analysisTextVotingRepository,
        FakeCurrentActorAccessor currentActorAccessor,
        FakeAuthenticationAttemptLimiter authenticationAttemptLimiter)
    {
        ModelClient = modelClient;
        AnalysisCaptureScheduler = analysisCaptureScheduler;
        Clock = clock;
        AnalysisTextVotingRepository = analysisTextVotingRepository;
        CurrentActorAccessor = currentActorAccessor;
        AuthenticationAttemptLimiter = authenticationAttemptLimiter;
        AnalyzeTextHandler = new AnalyzeTextHandler(modelClient, analysisTextVotingRepository, currentActorAccessor, clock);
        AnalyzeBatchHandler = new AnalyzeBatchHandler(modelClient, analysisCaptureScheduler, currentActorAccessor, clock);
        GetRandomTextHandler = new GetRandomTextHandler(analysisTextVotingRepository);
        GetTextByIdHandler = new GetTextByIdHandler(analysisTextVotingRepository);
        VoteTextHandler = new VoteTextHandler(analysisTextVotingRepository, currentActorAccessor);
    }

    public FakeModelPredictionClient ModelClient { get; }

    public FakeAnalysisCaptureScheduler AnalysisCaptureScheduler { get; }

    public FakeClock Clock { get; }

    public FakeAnalysisTextVotingRepository AnalysisTextVotingRepository { get; }

    public FakeCurrentActorAccessor CurrentActorAccessor { get; }

    public FakeAuthenticationAttemptLimiter AuthenticationAttemptLimiter { get; }

    public AnalyzeTextHandler AnalyzeTextHandler { get; }

    public AnalyzeBatchHandler AnalyzeBatchHandler { get; }

    public GetRandomTextHandler GetRandomTextHandler { get; }

    public GetTextByIdHandler GetTextByIdHandler { get; }

    public VoteTextHandler VoteTextHandler { get; }

    public static TestFixture Create()
    {
        var modelClient = new FakeModelPredictionClient();
        var analysisCaptureScheduler = new FakeAnalysisCaptureScheduler();
        var clock = new FakeClock(new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero));
        var analysisTextVotingRepository = new FakeAnalysisTextVotingRepository();
        var currentActorAccessor = new FakeCurrentActorAccessor();
        var authenticationAttemptLimiter = new FakeAuthenticationAttemptLimiter();
        return new TestFixture(
            modelClient,
            analysisCaptureScheduler,
            clock,
            analysisTextVotingRepository,
            currentActorAccessor,
            authenticationAttemptLimiter);
    }
}

internal sealed class FakeAnalysisTextVotingRepository : IAnalysisTextVotingRepository
{
    public AnalysisTextVotingCandidate? RandomCandidate { get; set; }

    public AnalysisTextVotingDetails? Details { get; set; }

    public bool RegisterVoteResult { get; set; } = true;

    public Guid? EnsuredVoteableTextId { get; set; } = Guid.NewGuid();

    public List<(Guid Id, AnalysisTextVoteKind Vote, CurrentActor Actor)> RegisteredVotes { get; } = [];

    public List<(ToxicityAnalysis Analysis, AnalysisTextOrigin Origin, CurrentActor Actor)> EnsuredVoteableTexts { get; } = [];

    public Task<Guid?> EnsureVoteableTextAsync(
        ToxicityAnalysis analysis,
        AnalysisTextOrigin origin,
        CurrentActor actor,
        CancellationToken cancellationToken)
    {
        EnsuredVoteableTexts.Add((analysis, origin, actor));
        return Task.FromResult(EnsuredVoteableTextId);
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

internal sealed class FakeAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public List<(ToxicityAnalysis Analysis, CurrentActor Actor)> CapturedAnalyses { get; } = [];

    public void Schedule(ToxicityAnalysis analysis, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        CapturedAnalyses.Add((analysis, actor));
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses, CurrentActor actor)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        CapturedAnalyses.AddRange(analyses.Select(analysis => (analysis, actor)));
    }
}

internal sealed class FakeCurrentActorAccessor : ICurrentActorAccessor
{
    public CurrentActor CurrentActor { get; set; } = CurrentActor.Anonymous("anonymous-test-actor");

    public CurrentActor GetCurrent()
    {
        return CurrentActor;
    }
}

internal sealed class FakeModelPredictionClient : IModelPredictionClient
{
    public ModelPrediction SinglePrediction { get; set; } = TestData.Prediction(PredictionLabel.NonToxic, 0.05m);

    public ExplainedModelPrediction ExplainedPrediction { get; set; } = TestData.ExplainedPrediction(PredictionLabel.NonToxic, 0.05m);

    public IReadOnlyList<ModelPrediction> BatchPredictions { get; set; } = [];

    public Exception? ExceptionToThrow { get; set; }

    public int PredictAsyncCallCount { get; private set; }

    public int PredictWithExplanationAsyncCallCount { get; private set; }

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
}

internal sealed class FakeClock : IClock
{
    public FakeClock(DateTimeOffset utcNow)
    {
        UtcNow = utcNow;
    }

    public DateTimeOffset UtcNow { get; }
}

internal sealed class FakeAuthenticationAttemptLimiter : IAuthenticationAttemptLimiter
{
    public HashSet<string> BlockedLogins { get; } = new(StringComparer.OrdinalIgnoreCase);

    public HashSet<string> BlockedServiceClients { get; } = new(StringComparer.OrdinalIgnoreCase);

    public List<string> LoginFailures { get; } = [];

    public List<string> ServiceTokenFailures { get; } = [];

    public List<string> LoginResets { get; } = [];

    public List<string> ServiceTokenResets { get; } = [];

    public void ThrowIfLoginBlocked(string email)
    {
        if (BlockedLogins.Contains(email))
        {
            throw new RateLimitExceededException("login blocked", TimeSpan.FromMinutes(5));
        }
    }

    public void RecordLoginFailure(string email)
    {
        LoginFailures.Add(email);
    }

    public void ResetLoginFailures(string email)
    {
        LoginResets.Add(email);
    }

    public void ThrowIfServiceTokenBlocked(string clientId)
    {
        if (BlockedServiceClients.Contains(clientId))
        {
            throw new RateLimitExceededException("service token blocked", TimeSpan.FromMinutes(5));
        }
    }

    public void RecordServiceTokenFailure(string clientId)
    {
        ServiceTokenFailures.Add(clientId);
    }

    public void ResetServiceTokenFailures(string clientId)
    {
        ServiceTokenResets.Add(clientId);
    }
}

internal static class TestData
{
    public static ModelPrediction Prediction(PredictionLabel label, decimal probability)
    {
        return new ModelPrediction(
            label,
            new ToxicProbability(probability),
            ModelIdentity.Create("baseline-a", "v1"));
    }

    public static ExplainedModelPrediction ExplainedPrediction(PredictionLabel label, decimal probability)
    {
        return new ExplainedModelPrediction(
            Prediction(label, probability),
            new ModelPredictionExplanation(
                0.89m,
                probability,
                0.80m,
                [new ModelPredictionFeature("strong_insult_count", 0.42m)]));
    }

    public static ToxicityAnalysis Analysis(
        string text,
        PredictionLabel label,
        decimal probability,
        DateTimeOffset createdAt)
    {
        return ToxicityAnalysis.Create(
            TextContent.Create(text),
            label,
            new ToxicProbability(probability),
            ModelIdentity.Create("baseline-a", "v1"),
            createdAt);
    }
}
