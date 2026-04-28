using System.Net;
using System.Text;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Texts;
using ToxicAnalyzer.Infrastructure.ModelService;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class ModelServiceClientTests
{
    [Fact]
    public async Task PredictAsync_MapsPredictResponse()
    {
        var handler = new StubHttpMessageHandler((request, cancellationToken) =>
        {
            Assert.Equal(HttpMethod.Post, request.Method);
            Assert.Equal("http://localhost:8000/v1/predict", request.RequestUri?.ToString());
            return Task.FromResult(CreateJsonResponse("""
                {
                  "label": 1,
                  "toxic_probability": 0.91,
                  "model_key": "baseline-a",
                  "model_version": "v3.3"
                }
                """));
        });

        var client = CreateClient(handler);

        var result = await client.PredictAsync(TextContent.Create("ты идиот"), CancellationToken.None);

        Assert.Equal(1, result.Label.Value);
        Assert.Equal(0.91m, result.ToxicProbability.Value);
        Assert.Equal("baseline-a", result.Model.ModelKey);
        Assert.Equal("v3.3", result.Model.ModelVersion);
    }

    [Fact]
    public async Task PredictBatchAsync_MapsBatchResponse()
    {
        var handler = new StubHttpMessageHandler((request, cancellationToken) =>
        {
            Assert.Equal("http://localhost:8000/v1/predict/batch", request.RequestUri?.ToString());
            return Task.FromResult(CreateJsonResponse("""
                {
                  "model_key": "baseline-a",
                  "model_version": "v3.3",
                  "items": [
                    { "label": 0, "toxic_probability": 0.10 },
                    { "label": 1, "toxic_probability": 0.90 }
                  ]
                }
                """));
        });

        var client = CreateClient(handler);

        var result = await client.PredictBatchAsync(
            [TextContent.Create("first"), TextContent.Create("second")],
            CancellationToken.None);

        Assert.Equal(2, result.Count);
        Assert.Equal([0, 1], result.Select(item => item.Label.Value).ToArray());
        Assert.Equal([0.10m, 0.90m], result.Select(item => item.ToxicProbability.Value).ToArray());
        Assert.All(result, item => Assert.Equal("baseline-a", item.Model.ModelKey));
    }

    [Fact]
    public async Task PredictBatchAsync_ThrowsWhenResponseCountMismatchesRequest()
    {
        var handler = new StubHttpMessageHandler((request, cancellationToken) =>
            Task.FromResult(CreateJsonResponse("""
                {
                  "model_key": "baseline-a",
                  "model_version": "v3.3",
                  "items": [
                    { "label": 0, "toxic_probability": 0.10 }
                  ]
                }
                """)));

        var client = CreateClient(handler);

        var exception = await Assert.ThrowsAsync<ModelServiceException>(() => client.PredictBatchAsync(
            [TextContent.Create("first"), TextContent.Create("second")],
            CancellationToken.None));

        Assert.Equal("Model service returned a batch response with an unexpected number of items.", exception.Message);
    }

    [Fact]
    public async Task PredictAsync_ThrowsForServerErrors()
    {
        var handler = new StubHttpMessageHandler((request, cancellationToken) =>
            Task.FromResult(new HttpResponseMessage(HttpStatusCode.InternalServerError)));

        var client = CreateClient(handler);

        var exception = await Assert.ThrowsAsync<ModelServiceException>(() => client.PredictAsync(
            TextContent.Create("hello"),
            CancellationToken.None));

        Assert.Equal(HttpStatusCode.InternalServerError, exception.StatusCode);
    }

    [Fact]
    public async Task PredictAsync_ThrowsForTimeouts()
    {
        var handler = new StubHttpMessageHandler((request, cancellationToken) =>
            throw new TaskCanceledException("timeout"));

        var client = CreateClient(handler);

        var exception = await Assert.ThrowsAsync<ModelServiceException>(() => client.PredictAsync(
            TextContent.Create("hello"),
            CancellationToken.None));

        Assert.Equal("Timed out while calling model service.", exception.Message);
    }

    private static IModelPredictionClient CreateClient(HttpMessageHandler handler)
    {
        var httpClient = new HttpClient(handler)
        {
            BaseAddress = new Uri("http://localhost:8000/"),
            Timeout = TimeSpan.FromSeconds(10)
        };

        return new ModelServiceClient(httpClient);
    }

    private static HttpResponseMessage CreateJsonResponse(string json)
    {
        return new HttpResponseMessage(HttpStatusCode.OK)
        {
            Content = new StringContent(json, Encoding.UTF8, "application/json")
        };
    }

    private sealed class StubHttpMessageHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> _handler;

        public StubHttpMessageHandler(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> handler)
        {
            _handler = handler;
        }

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            return _handler(request, cancellationToken);
        }
    }
}
