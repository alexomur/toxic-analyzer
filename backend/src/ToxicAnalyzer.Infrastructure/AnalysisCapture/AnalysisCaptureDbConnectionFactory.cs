using Microsoft.Extensions.Options;
using Npgsql;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public sealed class AnalysisCaptureDbConnectionFactory
{
    private readonly string _normalizedConnectionString;

    public AnalysisCaptureDbConnectionFactory(IOptions<AnalysisCaptureOptions> options)
    {
        _normalizedConnectionString = AnalysisCaptureConnectionString.Normalize(options.Value.ConnectionString);
    }

    public async Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        var connection = new NpgsqlConnection(_normalizedConnectionString);
        await connection.OpenAsync(cancellationToken);
        return connection;
    }
}
