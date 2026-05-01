namespace ToxicAnalyzer.Api.Contracts.Toxicity;

public sealed record GetRandomTextResponse(
    string TextId,
    string Text);
