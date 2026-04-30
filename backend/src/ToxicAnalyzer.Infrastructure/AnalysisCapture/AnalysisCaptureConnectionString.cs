using Npgsql;

namespace ToxicAnalyzer.Infrastructure.AnalysisCapture;

public static class AnalysisCaptureConnectionString
{
    public static string Normalize(string? connectionString)
    {
        if (string.IsNullOrWhiteSpace(connectionString))
        {
            throw new InvalidOperationException("Analysis capture connection string is required.");
        }

        if (!Uri.TryCreate(connectionString, UriKind.Absolute, out var uri) ||
            (uri.Scheme != "postgresql" && uri.Scheme != "postgres"))
        {
            return connectionString;
        }

        var builder = new NpgsqlConnectionStringBuilder
        {
            Host = uri.Host,
            Port = uri.IsDefaultPort ? 5432 : uri.Port,
            Database = uri.AbsolutePath.TrimStart('/'),
            SslMode = SslMode.Disable
        };

        if (!string.IsNullOrWhiteSpace(uri.UserInfo))
        {
            var parts = uri.UserInfo.Split(':', 2);
            if (parts.Length > 0)
            {
                builder.Username = Uri.UnescapeDataString(parts[0]);
            }

            if (parts.Length > 1)
            {
                builder.Password = Uri.UnescapeDataString(parts[1]);
            }
        }

        if (!string.IsNullOrWhiteSpace(uri.Query))
        {
            var query = uri.Query.TrimStart('?')
                .Split('&', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);

            foreach (var part in query)
            {
                var keyValue = part.Split('=', 2);
                if (keyValue.Length != 2)
                {
                    continue;
                }

                var key = Uri.UnescapeDataString(keyValue[0]);
                var value = Uri.UnescapeDataString(keyValue[1]);

                switch (key.ToLowerInvariant())
                {
                    case "sslmode":
                        if (Enum.TryParse<SslMode>(value, ignoreCase: true, out var sslMode))
                        {
                            builder.SslMode = sslMode;
                        }
                        break;
                    case "search_path":
                    case "searchpath":
                        builder.SearchPath = value;
                        break;
                    default:
                        break;
                }
            }
        }

        return builder.ConnectionString;
    }
}
