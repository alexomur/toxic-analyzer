using System.Security.Cryptography;

using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class PasswordHasher : IPasswordHasher
{
    private const int SaltSize = 16;
    private const int KeySize = 32;
    private const int Iterations = 100_000;

    public string HashPassword(string value)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(value);

        Span<byte> salt = stackalloc byte[SaltSize];
        RandomNumberGenerator.Fill(salt);
        var saltBytes = salt.ToArray();
        var valueBytes = System.Text.Encoding.UTF8.GetBytes(value);
        var key = Rfc2898DeriveBytes.Pbkdf2(valueBytes, saltBytes, Iterations, HashAlgorithmName.SHA256, KeySize);

        return $"{Iterations}.{Convert.ToBase64String(saltBytes)}.{Convert.ToBase64String(key)}";
    }

    public bool VerifyPassword(string value, string passwordHash)
    {
        if (string.IsNullOrWhiteSpace(value) || string.IsNullOrWhiteSpace(passwordHash))
        {
            return false;
        }

        var segments = passwordHash.Split('.', 3, StringSplitOptions.TrimEntries);
        if (segments.Length != 3 || !int.TryParse(segments[0], out var iterations))
        {
            return false;
        }

        var salt = Convert.FromBase64String(segments[1]);
        var expectedKey = Convert.FromBase64String(segments[2]);

        var valueBytes = System.Text.Encoding.UTF8.GetBytes(value);
        var actualKey = Rfc2898DeriveBytes.Pbkdf2(valueBytes, salt, iterations, HashAlgorithmName.SHA256, expectedKey.Length);
        return CryptographicOperations.FixedTimeEquals(actualKey, expectedKey);
    }
}
