namespace ToxicAnalyzer.Application.Abstractions;

public interface IClock
{
    DateTimeOffset UtcNow { get; }
}
