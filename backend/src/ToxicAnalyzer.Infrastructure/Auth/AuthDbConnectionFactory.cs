using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public class AuthDbConnectionFactory
{
    private readonly AuthOptions _options;

    public AuthDbConnectionFactory(IOptions<AuthOptions> options)
    {
        _options = options.Value;
    }

    public virtual async Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(_options.ConnectionString))
        {
            throw new InvalidOperationException("Auth:ConnectionString must be configured.");
        }

        var connection = new NpgsqlConnection(AuthConnectionString.Normalize(_options.ConnectionString));
        await connection.OpenAsync(cancellationToken);
        return connection;
    }
}
