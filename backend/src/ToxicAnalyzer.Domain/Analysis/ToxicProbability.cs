namespace ToxicAnalyzer.Domain.Analysis;

public readonly record struct ToxicProbability
{
    public ToxicProbability(decimal value)
    {
        if (value < 0m || value > 1m)
        {
            throw new ArgumentOutOfRangeException(nameof(value), value, "Probability must be within [0, 1].");
        }

        Value = value;
    }

    public decimal Value { get; }

    public override string ToString() => Value.ToString(System.Globalization.CultureInfo.InvariantCulture);
}
