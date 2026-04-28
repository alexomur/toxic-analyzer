using ToxicAnalyzer.Domain.Analysis;

namespace ToxicAnalyzer.Application.Abstractions;

public sealed record ModelPrediction(
    PredictionLabel Label,
    ToxicProbability ToxicProbability,
    ModelIdentity Model);
