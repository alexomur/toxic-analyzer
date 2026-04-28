using ToxicAnalyzer.Domain.Analysis;
using ToxicAnalyzer.Domain.Common;
using ToxicAnalyzer.Domain.Texts;

namespace ToxicAnalyzer.Domain.Candidates;

public sealed class CandidateText : Entity<CandidateTextId>
{
    private CandidateText(CandidateTextId id, ToxicityAnalysis analysis) : base(id)
    {
        Text = analysis.Text;
        TextFingerprint = analysis.TextFingerprint;
        FirstSeenAt = analysis.CreatedAt;
        LastSeenAt = analysis.CreatedAt;
        AnalysisCount = 1;
        LastAnalysisId = analysis.Id;
        LastLabel = analysis.Label;
        LastToxicProbability = analysis.ToxicProbability;
        LastModel = analysis.Model;
    }

    public TextContent Text { get; }

    public TextFingerprint TextFingerprint { get; }

    public DateTimeOffset FirstSeenAt { get; }

    public DateTimeOffset LastSeenAt { get; private set; }

    public int AnalysisCount { get; private set; }

    public AnalysisId LastAnalysisId { get; private set; }

    public PredictionLabel LastLabel { get; private set; }

    public ToxicProbability LastToxicProbability { get; private set; }

    public ModelIdentity LastModel { get; private set; }

    public static CandidateText CreateFromAnalysis(ToxicityAnalysis analysis, CandidateTextId? id = null)
    {
        ArgumentNullException.ThrowIfNull(analysis);

        return new CandidateText(id ?? CandidateTextId.New(), analysis);
    }

    public void RegisterAnalysis(ToxicityAnalysis analysis)
    {
        ArgumentNullException.ThrowIfNull(analysis);

        if (analysis.TextFingerprint != TextFingerprint || analysis.Text.Normalized != Text.Normalized)
        {
            throw new InvalidOperationException("Analysis text does not match this candidate text.");
        }

        AnalysisCount++;

        if (analysis.CreatedAt < LastSeenAt)
        {
            return;
        }

        LastSeenAt = analysis.CreatedAt;
        LastAnalysisId = analysis.Id;
        LastLabel = analysis.Label;
        LastToxicProbability = analysis.ToxicProbability;
        LastModel = analysis.Model;
    }
}
