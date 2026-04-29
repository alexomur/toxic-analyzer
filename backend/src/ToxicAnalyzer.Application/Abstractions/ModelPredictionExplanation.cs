namespace ToxicAnalyzer.Application.Abstractions;

public sealed record ModelPredictionExplanation(
    decimal CalibratedProbability,
    decimal AdjustedProbability,
    decimal Threshold,
    IReadOnlyList<ModelPredictionFeature> Features);

public sealed record ModelPredictionFeature(
    string Name,
    decimal Contribution);
