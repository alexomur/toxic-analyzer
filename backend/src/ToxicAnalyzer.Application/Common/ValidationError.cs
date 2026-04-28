namespace ToxicAnalyzer.Application.Common;

public sealed record ValidationError(string Field, string Message);
