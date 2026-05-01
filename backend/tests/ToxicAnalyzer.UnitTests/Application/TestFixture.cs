using ToxicAnalyzer.Application.Abstractions;
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
        FakeAnalysisTextVotingRepository analysisTextVotingRepository)
    {
        ModelClient = modelClient;
        AnalysisCaptureScheduler = analysisCaptureScheduler;
        Clock = clock;
        AnalysisTextVotingRepository = analysisTextVotingRepository;
        AnalyzeTextHandler = new AnalyzeTextHandler(modelClient, analysisCaptureScheduler, clock);
        AnalyzeBatchHandler = new AnalyzeBatchHandler(modelClient, analysisCaptureScheduler, clock);
        GetRandomTextHandler = new GetRandomTextHandler(analysisTextVotingRepository);
        GetTextByIdHandler = new GetTextByIdHandler(analysisTextVotingRepository);
        VoteTextHandler = new VoteTextHandler(analysisTextVotingRepository);
    }

    public FakeModelPredictionClient ModelClient { get; }

    public FakeAnalysisCaptureScheduler AnalysisCaptureScheduler { get; }

    public FakeClock Clock { get; }

    public FakeAnalysisTextVotingRepository AnalysisTextVotingRepository { get; }

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
        return new TestFixture(modelClient, analysisCaptureScheduler, clock, analysisTextVotingRepository);
    }
}

internal sealed class FakeAnalysisTextVotingRepository : IAnalysisTextVotingRepository
{
    public AnalysisTextVotingCandidate? RandomCandidate { get; set; }

    public AnalysisTextVotingDetails? Details { get; set; }

    public bool RegisterVoteResult { get; set; } = true;

    public List<(Guid Id, AnalysisTextVoteKind Vote)> RegisteredVotes { get; } = [];

    public Task<AnalysisTextVotingCandidate?> GetRandomAsync(CancellationToken cancellationToken)
    {
        return Task.FromResult(RandomCandidate);
    }

    public Task<AnalysisTextVotingDetails?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
    {
        return Task.FromResult(Details);
    }

    public Task<bool> RegisterVoteAsync(Guid id, AnalysisTextVoteKind vote, CancellationToken cancellationToken)
    {
        RegisteredVotes.Add((id, vote));
        return Task.FromResult(RegisterVoteResult);
    }
}

internal sealed class FakeAnalysisCaptureScheduler : IAnalysisCaptureScheduler
{
    public List<ToxicityAnalysis> CapturedAnalyses { get; } = [];

    public void Schedule(ToxicityAnalysis analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);
        CapturedAnalyses.Add(analysis);
    }

    public void ScheduleBatch(IReadOnlyCollection<ToxicityAnalysis> analyses)
    {
        ArgumentNullException.ThrowIfNull(analyses);
        CapturedAnalyses.AddRange(analyses);
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
