using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.IntegrationTests;

public sealed class ToxicityEndpointsTests : IClassFixture<ApiWebApplicationFactory>
{
    private static readonly JsonSerializerOptions JsonOptions = new(JsonSerializerDefaults.Web);

    private readonly ApiWebApplicationFactory _factory;
    private readonly HttpClient _client;

    public ToxicityEndpointsTests(ApiWebApplicationFactory factory)
    {
        _factory = factory;
        _factory.ModelPredictionClient.Reset();
        _factory.AnalysisCaptureScheduler.Reset();
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task Analyze_WithoutReportLevel_ReturnsSummaryResponse()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.SinglePrediction = FakeModelPredictionClient.CreatePrediction(1, 0.91m);

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "some text"
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeTextResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.AnalysisId));
        Assert.Equal(1, payload.Label);
        Assert.Equal(0.91m, payload.ToxicProbability);
        Assert.Equal("baseline", payload.Model.ModelKey);
        Assert.Equal("v3.3", payload.Model.ModelVersion);
        Assert.Equal("summary", payload.ReportLevel);
        Assert.Null(payload.Explanation);
        Assert.Equal(new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero), payload.CreatedAt);
        Assert.Equal(1, _factory.ModelPredictionClient.PredictAsyncCallCount);
        Assert.Equal(0, _factory.ModelPredictionClient.PredictWithExplanationAsyncCallCount);
    }

    [Fact]
    public async Task Analyze_WithSummaryReportLevel_ReturnsSummaryResponse()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.SinglePrediction = FakeModelPredictionClient.CreatePrediction(1, 0.91m);

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "some text",
            reportLevel = "summary"
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeTextResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Equal("summary", payload.ReportLevel);
        Assert.Null(payload.Explanation);
        Assert.Equal(1, _factory.ModelPredictionClient.PredictAsyncCallCount);
        Assert.Equal(0, _factory.ModelPredictionClient.PredictWithExplanationAsyncCallCount);
        Assert.Single(_factory.AnalysisCaptureScheduler.CapturedAnalyses);
    }

    [Fact]
    public async Task Analyze_WithFullReportLevel_ReturnsFullResponse()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.ExplainedPrediction = FakeModelPredictionClient.CreateExplainedPrediction(1, 0.91m);

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "some text",
            reportLevel = "full"
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeTextResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Equal("full", payload.ReportLevel);
        Assert.NotNull(payload.Explanation);
        Assert.Equal(0.89m, payload.Explanation.CalibratedProbability);
        Assert.Equal(0.91m, payload.Explanation.AdjustedProbability);
        Assert.Equal(0.80m, payload.Explanation.Threshold);
        Assert.Single(payload.Explanation.Features);
        Assert.Equal("some feature", payload.Explanation.Features[0].Name);
        Assert.Equal(0.42m, payload.Explanation.Features[0].Contribution);
        Assert.Equal(0, _factory.ModelPredictionClient.PredictAsyncCallCount);
        Assert.Equal(1, _factory.ModelPredictionClient.PredictWithExplanationAsyncCallCount);
    }

    [Fact]
    public async Task Analyze_Returns400_ForWhitespaceText()
    {
        _factory.ModelPredictionClient.Reset();

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "   "
        });

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);

        var payload = await response.Content.ReadFromJsonAsync<ProblemDetailsContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Equal("Request validation failed.", payload.Title);
        Assert.Contains(payload.Errors, error => error.Field == "text");
    }

    [Fact]
    public async Task AnalyzeBatch_ReturnsSuccessfulResponse()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.BatchPredictions =
        [
            FakeModelPredictionClient.CreatePrediction(0, 0.12m),
            FakeModelPredictionClient.CreatePrediction(1, 0.88m)
        ];

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze-batch", new
        {
            items = new object[]
            {
                new { clientItemId = "a-1", text = "first" },
                new { clientItemId = "b-2", text = "second" }
            }
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeBatchResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.False(string.IsNullOrWhiteSpace(payload.BatchId));
        Assert.Equal(2, payload.Items.Count);
        Assert.Equal(2, payload.Summary.Total);
        Assert.Equal(1, payload.Summary.ToxicCount);
        Assert.Equal(1, payload.Summary.NonToxicCount);
        Assert.Equal(0.50m, payload.Summary.AverageToxicProbability);
        Assert.Equal(new DateTimeOffset(2026, 4, 29, 12, 0, 0, TimeSpan.Zero), payload.CreatedAt);
        Assert.Equal(2, _factory.AnalysisCaptureScheduler.CapturedAnalyses.Count);
    }

    [Fact]
    public async Task AnalyzeBatch_PreservesRequestOrder()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.BatchPredictions =
        [
            FakeModelPredictionClient.CreatePrediction(1, 0.90m),
            FakeModelPredictionClient.CreatePrediction(0, 0.10m)
        ];

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze-batch", new
        {
            items = new object[]
            {
                new { clientItemId = "first-id", text = "first" },
                new { clientItemId = "second-id", text = "second" }
            }
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeBatchResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Collection(
            payload.Items,
            item => Assert.Equal("first-id", item.ClientItemId),
            item => Assert.Equal("second-id", item.ClientItemId));
        Assert.Equal([1, 0], payload.Items.Select(item => item.Label).ToArray());
    }

    [Fact]
    public async Task AnalyzeBatch_ReturnsClientItemIdWithoutChanges()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.BatchPredictions =
        [
            FakeModelPredictionClient.CreatePrediction(0, 0.22m),
            FakeModelPredictionClient.CreatePrediction(0, 0.33m)
        ];

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze-batch", new
        {
            items = new object[]
            {
                new { clientItemId = " original-id ", text = "first" },
                new { clientItemId = (string?)null, text = "second" }
            }
        });

        response.EnsureSuccessStatusCode();

        var payload = await response.Content.ReadFromJsonAsync<AnalyzeBatchResponseContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Equal(" original-id ", payload.Items[0].ClientItemId);
        Assert.Null(payload.Items[1].ClientItemId);
    }

    [Fact]
    public async Task AnalyzeBatch_Returns400_ForEmptyBatch()
    {
        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze-batch", new
        {
            items = Array.Empty<object>()
        });

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);

        var payload = await response.Content.ReadFromJsonAsync<ProblemDetailsContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Contains(payload.Errors, error => error.Field == "items");
    }

    [Fact]
    public async Task Analyze_Returns503_WhenModelServiceFails()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.ExceptionToThrow = new ModelServiceException("model down")
        {
            FailureKind = ModelServiceFailureKind.Unavailable
        };

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "some text"
        });

        Assert.Equal(HttpStatusCode.ServiceUnavailable, response.StatusCode);

        var payload = await response.Content.ReadFromJsonAsync<ProblemDetailsContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Equal("Model service unavailable.", payload.Title);
        Assert.Equal("model down", payload.Detail);
    }

    [Fact]
    public async Task Analyze_ResponseShapeMatchesPublicContract()
    {
        _factory.ModelPredictionClient.Reset();
        _factory.ModelPredictionClient.SinglePrediction = FakeModelPredictionClient.CreatePrediction(1, 0.91m);

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "shape test"
        });

        response.EnsureSuccessStatusCode();

        using var document = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
        var root = document.RootElement;

        Assert.True(root.TryGetProperty("analysisId", out _));
        Assert.True(root.TryGetProperty("label", out _));
        Assert.True(root.TryGetProperty("toxicProbability", out _));
        Assert.True(root.TryGetProperty("model", out var model));
        Assert.True(root.TryGetProperty("reportLevel", out _));
        Assert.True(root.TryGetProperty("explanation", out _));
        Assert.True(root.TryGetProperty("createdAt", out _));
        Assert.True(model.TryGetProperty("modelKey", out _));
        Assert.True(model.TryGetProperty("modelVersion", out _));
    }

    [Fact]
    public async Task Analyze_Returns400_ForInvalidReportLevel()
    {
        _factory.ModelPredictionClient.Reset();

        var response = await _client.PostAsJsonAsync("/api/v1/toxicity/analyze", new
        {
            text = "some text",
            reportLevel = "verbose"
        });

        Assert.Equal(HttpStatusCode.BadRequest, response.StatusCode);

        var payload = await response.Content.ReadFromJsonAsync<ProblemDetailsContract>(JsonOptions);

        Assert.NotNull(payload);
        Assert.Contains(payload.Errors, error => error.Field == "reportLevel");
    }

    private sealed record AnalyzeTextResponseContract(
        string AnalysisId,
        int Label,
        decimal ToxicProbability,
        ModelInfoContract Model,
        string ReportLevel,
        AnalyzeTextExplanationContract? Explanation,
        DateTimeOffset CreatedAt);

    private sealed record AnalyzeTextExplanationContract(
        decimal CalibratedProbability,
        decimal AdjustedProbability,
        decimal Threshold,
        IReadOnlyList<AnalyzeTextExplanationFeatureContract> Features);

    private sealed record AnalyzeTextExplanationFeatureContract(
        string Name,
        decimal Contribution);

    private sealed record AnalyzeBatchResponseContract(
        string BatchId,
        IReadOnlyList<AnalyzeBatchItemContract> Items,
        BatchSummaryContract Summary,
        DateTimeOffset CreatedAt);

    private sealed record AnalyzeBatchItemContract(
        string? ClientItemId,
        string AnalysisId,
        int Label,
        decimal ToxicProbability,
        ModelInfoContract Model);

    private sealed record BatchSummaryContract(
        int Total,
        int ToxicCount,
        int NonToxicCount,
        decimal AverageToxicProbability);

    private sealed record ModelInfoContract(string ModelKey, string ModelVersion);

    private sealed record ProblemDetailsContract(
        string Title,
        string? Detail,
        IReadOnlyList<ValidationErrorContract> Errors);

    private sealed record ValidationErrorContract(string Field, string Message);
}
