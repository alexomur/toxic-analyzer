using System.Net.Http.Json;
using System.Text.Json;
using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Infrastructure.ModelService;

public sealed class ModelServiceClient : IModelPredictionClient
{
    private static readonly JsonSerializerOptions SerializerOptions = new(JsonSerializerDefaults.Web);

    private readonly HttpClient _httpClient;

    public ModelServiceClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<ModelPrediction> PredictAsync(TextContent text, CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(text);

        var response = await PostAsJsonAsync<PredictRequestDto, PredictResponseDto>(
            "v1/predict",
            new PredictRequestDto(text.Original),
            cancellationToken);

        return MapPrediction(response.Label, response.ToxicProbability, response.ModelKey, response.ModelVersion);
    }

    public async Task<IReadOnlyList<ModelPrediction>> PredictBatchAsync(
        IReadOnlyList<TextContent> texts,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(texts);

        var payload = new BatchPredictRequestDto(
            texts.Select(text => new BatchPredictRequestItemDto(text.Original)).ToArray());

        var response = await PostAsJsonAsync<BatchPredictRequestDto, BatchPredictResponseDto>(
            "v1/predict/batch",
            payload,
            cancellationToken);

        if (response.Items.Count != texts.Count)
        {
            throw new ModelServiceException("Model service returned a batch response with an unexpected number of items.");
        }

        return response.Items
            .Select(item => MapPrediction(item.Label, item.ToxicProbability, response.ModelKey, response.ModelVersion))
            .ToArray();
    }

    private async Task<TResponse> PostAsJsonAsync<TRequest, TResponse>(
        string requestUri,
        TRequest payload,
        CancellationToken cancellationToken)
    {
        HttpResponseMessage response;

        try
        {
            response = await _httpClient.PostAsJsonAsync(requestUri, payload, SerializerOptions, cancellationToken);
        }
        catch (TaskCanceledException exception) when (!cancellationToken.IsCancellationRequested)
        {
            throw new ModelServiceException("Timed out while calling model service.", exception)
            {
                FailureKind = ModelServiceFailureKind.Timeout
            };
        }
        catch (HttpRequestException exception)
        {
            throw new ModelServiceException("Failed to reach model service.", exception)
            {
                StatusCode = exception.StatusCode,
                FailureKind = ModelServiceFailureKind.Unavailable
            };
        }

        if (!response.IsSuccessStatusCode)
        {
            throw new ModelServiceException(
                $"Model service returned HTTP {(int)response.StatusCode} ({response.StatusCode}).")
            {
                StatusCode = response.StatusCode,
                FailureKind = ModelServiceFailureKind.Unavailable
            };
        }

        try
        {
            var result = await response.Content.ReadFromJsonAsync<TResponse>(SerializerOptions, cancellationToken);
            if (result is null)
            {
                throw new ModelServiceException("Model service returned an empty response body.");
            }

            return result;
        }
        catch (ModelServiceException)
        {
            throw;
        }
        catch (NotSupportedException exception)
        {
            throw new ModelServiceException("Model service returned an unsupported content type.", exception)
            {
                StatusCode = response.StatusCode,
                FailureKind = ModelServiceFailureKind.Unavailable
            };
        }
        catch (JsonException exception)
        {
            throw new ModelServiceException("Model service returned malformed JSON.", exception)
            {
                StatusCode = response.StatusCode,
                FailureKind = ModelServiceFailureKind.Unavailable
            };
        }
    }

    private static ModelPrediction MapPrediction(
        int label,
        double toxicProbability,
        string modelKey,
        string modelVersion)
    {
        try
        {
            return new ModelPrediction(
                PredictionLabel.FromInt(label),
                new ToxicProbability(Convert.ToDecimal(toxicProbability)),
                ModelIdentity.Create(modelKey, modelVersion));
        }
        catch (Exception exception) when (exception is ArgumentException or ArgumentOutOfRangeException or OverflowException)
        {
            throw new ModelServiceException("Model service returned an invalid prediction payload.", exception);
        }
    }
}
