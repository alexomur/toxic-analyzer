namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed record AnalysisTextUpsertRecord(
    Guid Id,
    string TextFingerprint,
    string NormalizedText,
    int TextLength,
    long RequestCount,
    int LastLabel,
    decimal LastToxicProbability,
    string LastModelKey,
    string LastModelVersion,
    string SourceKind,
    string? ActorId,
    string? TenantId,
    DateTimeOffset CreatedAt,
    DateTimeOffset LastSeenAt);
