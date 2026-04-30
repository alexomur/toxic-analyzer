namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public static class AnalysisTextBatchAggregator
{
    public static IReadOnlyList<AnalysisTextUpsertRecord> Aggregate(IReadOnlyCollection<AnalysisCaptureMessage> messages)
    {
        ArgumentNullException.ThrowIfNull(messages);

        if (messages.Count == 0)
        {
            return [];
        }

        var grouped = new Dictionary<string, AggregationState>(StringComparer.Ordinal);

        foreach (var message in messages)
        {
            if (grouped.TryGetValue(message.TextFingerprint, out var state))
            {
                state.RequestCount++;

                if (message.CapturedAt >= state.LastSeenAt)
                {
                    state.LastSeenAt = message.CapturedAt;
                    state.LastLabel = message.Label.Value;
                    state.LastToxicProbability = message.ToxicProbability.Value;
                    state.LastModelKey = message.Model.ModelKey;
                    state.LastModelVersion = message.Model.ModelVersion;
                    state.SourceKind = message.SourceKind;
                    state.ActorId = message.ActorId;
                    state.TenantId = message.TenantId;
                }

                grouped[message.TextFingerprint] = state;
                continue;
            }

            grouped[message.TextFingerprint] = new AggregationState
            {
                Id = Guid.NewGuid(),
                NormalizedText = message.NormalizedText,
                TextLength = message.NormalizedText.Length,
                RequestCount = 1,
                LastLabel = message.Label.Value,
                LastToxicProbability = message.ToxicProbability.Value,
                LastModelKey = message.Model.ModelKey,
                LastModelVersion = message.Model.ModelVersion,
                SourceKind = message.SourceKind,
                ActorId = message.ActorId,
                TenantId = message.TenantId,
                CreatedAt = message.CapturedAt,
                LastSeenAt = message.CapturedAt
            };
        }

        return grouped
            .Select(pair => new AnalysisTextUpsertRecord(
                pair.Value.Id,
                pair.Key,
                pair.Value.NormalizedText,
                pair.Value.TextLength,
                pair.Value.RequestCount,
                pair.Value.LastLabel,
                pair.Value.LastToxicProbability,
                pair.Value.LastModelKey,
                pair.Value.LastModelVersion,
                pair.Value.SourceKind,
                pair.Value.ActorId,
                pair.Value.TenantId,
                pair.Value.CreatedAt,
                pair.Value.LastSeenAt))
            .ToArray();
    }

    private sealed class AggregationState
    {
        public Guid Id { get; init; }

        public required string NormalizedText { get; init; }

        public int TextLength { get; init; }

        public long RequestCount { get; set; }

        public int LastLabel { get; set; }

        public decimal LastToxicProbability { get; set; }

        public required string LastModelKey { get; set; }

        public required string LastModelVersion { get; set; }

        public required string SourceKind { get; set; }

        public string? ActorId { get; set; }

        public string? TenantId { get; set; }

        public DateTimeOffset CreatedAt { get; init; }

        public DateTimeOffset LastSeenAt { get; set; }
    }
}
