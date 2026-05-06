using ToxicAnalyzer.Application.Abstractions;
using ToxicAnalyzer.Application.Auth;
using ToxicAnalyzer.Application.Common;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Application.Toxicity.AnalyzeText;

public sealed class AnalyzeTextHandler
{
    private readonly IModelPredictionClient _modelPredictionClient;
    private readonly IAnalysisTextVotingRepository _analysisTextVotingRepository;
    private readonly ICurrentActorAccessor _currentActorAccessor;
    private readonly IClock _clock;

    public AnalyzeTextHandler(
        IModelPredictionClient modelPredictionClient,
        IAnalysisTextVotingRepository analysisTextVotingRepository,
        ICurrentActorAccessor currentActorAccessor,
        IClock clock)
    {
        _modelPredictionClient = modelPredictionClient;
        _analysisTextVotingRepository = analysisTextVotingRepository;
        _currentActorAccessor = currentActorAccessor;
        _clock = clock;
    }

    public async Task<AnalyzeTextResult> HandleAsync(
        AnalyzeTextCommand command,
        CancellationToken cancellationToken)
    {
        ArgumentNullException.ThrowIfNull(command);

        var text = ToxicityRequestValidation.CreateTextContent(command.Text, "text");
        var reportLevel = ToxicityRequestValidation.ResolveReportLevel(command.ReportLevel);
        var (prediction, explanation) = await PredictAsync(text, reportLevel, cancellationToken);
        var analysis = ToxicityMappings.ToAnalysis(text, prediction, _clock.UtcNow);
        var actor = _currentActorAccessor.GetCurrent();
        Guid? textId = null;

        if (actor.HasCapability(AuthCapabilities.AnalysisSubmit))
        {
            var origin = actor.ActorType == ActorType.Service
                ? AnalysisTextOrigin.BotSubmitted
                : AnalysisTextOrigin.SelfSubmitted;
            textId = await _analysisTextVotingRepository.EnsureVoteableTextAsync(
                analysis,
                origin,
                actor,
                cancellationToken);
        }

        return new AnalyzeTextResult(
            analysis.Id.ToString(),
            textId?.ToString(),
            analysis.Label.Value,
            analysis.ToxicProbability.Value,
            ToxicityMappings.ToModelDescriptor(analysis.Model),
            reportLevel,
            explanation,
            analysis.CreatedAt);
    }

    private async Task<(ModelPrediction Prediction, AnalyzeTextExplanation? Explanation)> PredictAsync(
        TextContent text,
        AnalyzeTextReportLevel reportLevel,
        CancellationToken cancellationToken)
    {
        if (reportLevel == AnalyzeTextReportLevel.Full)
        {
            var explainedPrediction = await _modelPredictionClient.PredictWithExplanationAsync(text, cancellationToken);
            return (explainedPrediction.Prediction, MapExplanation(explainedPrediction.Explanation));
        }

        var prediction = await _modelPredictionClient.PredictAsync(text, cancellationToken);
        return (prediction, null);
    }

    private static AnalyzeTextExplanation MapExplanation(ModelPredictionExplanation explanation)
    {
        return new AnalyzeTextExplanation(
            explanation.CalibratedProbability,
            explanation.AdjustedProbability,
            explanation.Threshold,
            explanation.Features
                .Select(feature => new AnalyzeTextExplanationFeature(feature.Name, feature.Contribution))
                .ToArray());
    }
}
