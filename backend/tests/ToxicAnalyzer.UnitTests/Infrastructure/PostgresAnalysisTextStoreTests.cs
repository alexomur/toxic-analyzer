using ToxicAnalyzer.Infrastructure.AnalysisCapture;
using System.Reflection;

namespace ToxicAnalyzer.UnitTests.Infrastructure;

public sealed class PostgresAnalysisTextStoreTests
{
    [Fact]
    public void NormalizeConnectionString_ConvertsPostgresUriToNpgsqlFormat()
    {
        var normalized = AnalysisCaptureConnectionString.Normalize(
            "postgresql://toxic_model:toxic_model_pw@postgres:5432/toxic_analyzer");

        Assert.Contains("Host=postgres", normalized);
        Assert.Contains("Port=5432", normalized);
        Assert.Contains("Database=toxic_analyzer", normalized);
        Assert.Contains("Username=toxic_model", normalized);
        Assert.Contains("Password=toxic_model_pw", normalized);
    }

    [Fact]
    public void NormalizeConnectionString_KeepsRegularConnectionStringUntouched()
    {
        const string input = "Host=postgres;Port=5432;Database=toxic_analyzer;Username=toxic_model;Password=toxic_model_pw";

        var normalized = AnalysisCaptureConnectionString.Normalize(input);

        Assert.Equal(input, normalized);
    }

    [Fact]
    public void BuildGetRandomSql_IncludesOnlyTrustedOrigins()
    {
        var method = typeof(PostgresAnalysisTextVotingRepository).GetMethod(
            "BuildGetRandomSql",
            BindingFlags.NonPublic | BindingFlags.Static);

        Assert.NotNull(method);

        var sql = Assert.IsType<string>(method!.Invoke(null, ["public"]));

        Assert.DoesNotContain("'self_submitted'", sql);
        Assert.Contains("'bot_submitted'", sql);
        Assert.Contains("'random_pool'", sql);
    }
}
