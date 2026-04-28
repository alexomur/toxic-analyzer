using ToxicAnalyzer.Domain.Common;

namespace ToxicAnalyzer.Domain.Analysis;

public sealed class AnalysisBatchItem
{
    private AnalysisBatchItem(int position, ToxicityAnalysis analysis, ClientItemId? clientItemId)
    {
        Position = position;
        Analysis = analysis;
        ClientItemId = clientItemId;
    }

    public int Position { get; }

    public ToxicityAnalysis Analysis { get; }

    public ClientItemId? ClientItemId { get; }

    public static AnalysisBatchItem Create(int position, ToxicityAnalysis analysis, ClientItemId? clientItemId = null)
    {
        if (position < 0)
        {
            throw new ArgumentOutOfRangeException(nameof(position), position, "Position must be zero or greater.");
        }

        ArgumentNullException.ThrowIfNull(analysis);

        return new AnalysisBatchItem(position, analysis, clientItemId);
    }
}
