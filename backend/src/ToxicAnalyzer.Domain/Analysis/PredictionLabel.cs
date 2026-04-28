namespace ToxicAnalyzer.Domain.Analysis;

public readonly record struct PredictionLabel
{
    private PredictionLabel(int value)
    {
        Value = value;
    }

    public int Value { get; }

    public bool IsToxic => Value == 1;

    public static PredictionLabel NonToxic => new(0);

    public static PredictionLabel Toxic => new(1);

    public static PredictionLabel FromInt(int value)
    {
        return value switch
        {
            0 => NonToxic,
            1 => Toxic,
            _ => throw new ArgumentOutOfRangeException(nameof(value), value, "Prediction label must be 0 or 1."),
        };
    }

    public override string ToString() => Value.ToString();
}
