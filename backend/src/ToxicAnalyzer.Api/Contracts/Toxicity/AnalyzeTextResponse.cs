using System.ComponentModel;

namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeTextResponse(
    string AnalysisId,
    int Label,
    decimal ToxicProbability,
    ModelInfoResponse Model,
    [property: Description("Resolved report level used for this analysis: 'summary' or 'full'.")]
    string ReportLevel,
    AnalyzeTextExplanationResponse? Explanation,
    DateTimeOffset CreatedAt);

public sealed record AnalyzeTextExplanationResponse(
    decimal CalibratedProbability,
    decimal AdjustedProbability,
    decimal Threshold,
    IReadOnlyList<AnalyzeTextExplanationFeatureResponse> Features);

public sealed record AnalyzeTextExplanationFeatureResponse(
    string Name,
    decimal Contribution);
