namespace ToxicAnalyzer.Application.Toxicity.AnalyzeText;

public sealed record AnalyzeTextExplanation(
    decimal CalibratedProbability,
    decimal AdjustedProbability,
    decimal Threshold,
    IReadOnlyList<AnalyzeTextExplanationFeature> Features);

public sealed record AnalyzeTextExplanationFeature(
    string Name,
    decimal Contribution);
