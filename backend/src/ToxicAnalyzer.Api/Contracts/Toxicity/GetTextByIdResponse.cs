namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record GetTextByIdResponse(
    string TextId,
    string Text,
    int TextLength,
    long RequestCount,
    int LastLabel,
    decimal LastToxicProbability,
    ModelInfoResponse Model,
    int VotesToxic,
    int VotesNonToxic,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastSeenAt);
