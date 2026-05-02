namespace ToxicAnalyzer.Application.Auth.IssueServiceToken;

public sealed record IssueServiceTokenCommand(string ClientId, string ClientSecret);
