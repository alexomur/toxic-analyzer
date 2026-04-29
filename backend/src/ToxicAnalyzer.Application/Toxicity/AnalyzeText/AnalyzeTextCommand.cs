namespace ToxicAnalyzer.Application.Toxicity.AnalyzeText;

public sealed record AnalyzeTextCommand(string Text, string? ReportLevel = null);
