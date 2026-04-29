namespace ToxicAnalyzer.Application.Abstractions;

public sealed record ExplainedModelPrediction(
    ModelPrediction Prediction,
    ModelPredictionExplanation Explanation);
