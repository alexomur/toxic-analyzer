namespace ToxicAnalyzer.Domain.Analysis;

public readonly record struct AnalysisBatchId(Guid Value)
{
    public static AnalysisBatchId New() => new(Guid.NewGuid());

    public override string ToString() => Value.ToString();
}
