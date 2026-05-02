namespace ToxicAnalyzer.Application.Auth;

public interface IPasswordHasher
{
    string HashPassword(string value);

    bool VerifyPassword(string value, string passwordHash);
}
