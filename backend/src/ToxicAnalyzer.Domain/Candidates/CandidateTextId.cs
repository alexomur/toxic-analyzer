namespace ToxicAnalyzer.Domain.Candidates;

public readonly record struct CandidateTextId(Guid Value)
{
    public static CandidateTextId New() => new(Guid.NewGuid());

    public override string ToString() => Value.ToString();
}
