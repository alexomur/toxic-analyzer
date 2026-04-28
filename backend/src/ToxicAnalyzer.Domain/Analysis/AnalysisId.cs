namespace ToxicAnalyzer.Domain.Analysis;

public readonly record struct AnalysisId(Guid Value)
{
    public static AnalysisId New() => new(Guid.NewGuid());

    public override string ToString() => Value.ToString();
}
