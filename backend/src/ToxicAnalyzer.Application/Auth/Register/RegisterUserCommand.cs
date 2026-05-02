namespace ToxicAnalyzer.Application.Auth.Register;

public sealed record RegisterUserCommand(string Email, string Password, string? Username);
