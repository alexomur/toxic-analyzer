using ToxicAnalyzer.Domain.Common;

namespace ToxicAnalyzer.Domain.Analysis;

public sealed class AnalysisBatch : Entity<AnalysisBatchId>
{
    private readonly IReadOnlyList<AnalysisBatchItem> _items;

    private AnalysisBatch(
        AnalysisBatchId id,
        IReadOnlyList<AnalysisBatchItem> items,
        AnalysisBatchSummary summary,
        DateTimeOffset createdAt) : base(id)
    {
        _items = items;
        Summary = summary;
        CreatedAt = createdAt;
    }

    public IReadOnlyList<AnalysisBatchItem> Items => _items;

    public AnalysisBatchSummary Summary { get; }

    public DateTimeOffset CreatedAt { get; }

    public static AnalysisBatch Create(
        IEnumerable<AnalysisBatchItem> items,
        DateTimeOffset createdAt,
        AnalysisBatchId? id = null)
    {
        ArgumentNullException.ThrowIfNull(items);
        Guard.AgainstDefault(createdAt, nameof(createdAt));

        var materializedItems = items.OrderBy(item => item.Position).ToArray();
        if (materializedItems.Length == 0)
        {
            throw new ArgumentException("Batch must contain at least one item.", nameof(items));
        }

        for (var index = 0; index < materializedItems.Length; index++)
        {
            if (materializedItems[index].Position != index)
            {
                throw new ArgumentException("Batch item positions must form a contiguous zero-based sequence.", nameof(items));
            }
        }

        var toxicCount = materializedItems.Count(item => item.Analysis.Label.IsToxic);
        var total = materializedItems.Length;
        var nonToxicCount = total - toxicCount;
        var averageProbability = materializedItems.Average(item => item.Analysis.ToxicProbability.Value);

        return new AnalysisBatch(
            id ?? AnalysisBatchId.New(),
            materializedItems,
            new AnalysisBatchSummary(total, toxicCount, nonToxicCount, averageProbability),
            createdAt);
    }
}
