namespace ToxicAnalyzer.Application.Auth;

public interface ISessionTokenService
{
    string GenerateToken();

    string ComputeHash(string value);
}
