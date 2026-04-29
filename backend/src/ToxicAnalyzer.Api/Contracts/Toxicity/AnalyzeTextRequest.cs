using System.ComponentModel;

namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record AnalyzeTextRequest(
    string Text,
    [property: Description("Optional report level. Allowed values: 'summary' and 'full'. Defaults to 'summary' when omitted.")]
    string? ReportLevel = null);
