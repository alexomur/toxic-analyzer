using System.Text.Json.Serialization;

namespace ToxicAnalyzer.Infrastructure.ModelService;

internal sealed record PredictRequestDto(
    [property: JsonPropertyName("text")] string Text);

internal sealed record PredictResponseDto(
    [property: JsonPropertyName("label")] int Label,
    [property: JsonPropertyName("toxic_probability")] double ToxicProbability,
    [property: JsonPropertyName("model_key")] string ModelKey,
    [property: JsonPropertyName("model_version")] string ModelVersion);

internal sealed record BatchPredictRequestDto(
    [property: JsonPropertyName("items")] IReadOnlyList<BatchPredictRequestItemDto> Items);

internal sealed record BatchPredictRequestItemDto(
    [property: JsonPropertyName("text")] string Text);

internal sealed record BatchPredictResponseDto(
    [property: JsonPropertyName("model_key")] string ModelKey,
    [property: JsonPropertyName("model_version")] string ModelVersion,
    [property: JsonPropertyName("items")] IReadOnlyList<BatchPredictResponseItemDto> Items);

internal sealed record BatchPredictResponseItemDto(
    [property: JsonPropertyName("label")] int Label,
    [property: JsonPropertyName("toxic_probability")] double ToxicProbability);
