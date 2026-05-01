namespace ToxicAnalyzer.Application.Toxicity.VoteText;

public sealed record VoteTextCommand(
    Guid TextId,
    string Vote);
