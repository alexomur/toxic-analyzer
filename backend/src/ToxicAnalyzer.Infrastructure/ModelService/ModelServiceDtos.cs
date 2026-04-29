using System.Text.Json.Serialization;

namespace ToxicAnalyzer.Infrastructure.ModelService;

internal sealed record PredictRequestDto(
    [property: JsonPropertyName("text")] string Text);

internal sealed record PredictResponseDto(
    [property: JsonPropertyName("label")] int Label,
    [property: JsonPropertyName("toxic_probability")] double ToxicProbability,
    [property: JsonPropertyName("model_key")] string ModelKey,
    [property: JsonPropertyName("model_version")] string ModelVersion);

internal sealed record PredictExplainResponseDto(
    [property: JsonPropertyName("label")] int Label,
    [property: JsonPropertyName("toxic_probability")] double ToxicProbability,
    [property: JsonPropertyName("calibrated_probability")] double CalibratedProbability,
    [property: JsonPropertyName("posthoc_adjusted_probability")] double PosthocAdjustedProbability,
    [property: JsonPropertyName("threshold")] double Threshold,
    [property: JsonPropertyName("model_key")] string ModelKey,
    [property: JsonPropertyName("model_version")] string ModelVersion,
    [property: JsonPropertyName("explanation")] PredictExplainDetailsDto Explanation);

internal sealed record PredictExplainDetailsDto(
    [property: JsonPropertyName("top_positive_features")] IReadOnlyList<PredictExplainFeatureDto> TopPositiveFeatures,
    [property: JsonPropertyName("top_negative_features")] IReadOnlyList<PredictExplainFeatureDto> TopNegativeFeatures);

internal sealed record PredictExplainFeatureDto(
    [property: JsonPropertyName("feature_name")] string FeatureName,
    [property: JsonPropertyName("contribution")] double Contribution);

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
