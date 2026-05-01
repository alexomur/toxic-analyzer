namespace ToxicAnalyzer.Application.Toxicity.GetTextById;

public sealed record GetTextByIdResult(
    string TextId,
    string Text,
    int TextLength,
    long RequestCount,
    int LastLabel,
    decimal LastToxicProbability,
    string LastModelKey,
    string LastModelVersion,
    int VotesToxic,
    int VotesNonToxic,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastSeenAt);
