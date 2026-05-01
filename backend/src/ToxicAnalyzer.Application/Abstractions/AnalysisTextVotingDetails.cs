namespace ToxicAnalyzer.Application.Abstractions;

public sealed record AnalysisTextVotingDetails(
    Guid Id,
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
