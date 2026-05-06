using Microsoft.Extensions.Options;
using Npgsql;
using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class PostgresAuthStore : IAuthStore
{
    private readonly AuthOptions _options;
    private readonly AuthDbConnectionFactory _connectionFactory;
    private readonly AuthSchemaInitializer _schemaInitializer;

    public PostgresAuthStore(
        IOptions<AuthOptions> options,
        AuthDbConnectionFactory connectionFactory,
        AuthSchemaInitializer schemaInitializer)
    {
        _options = options.Value;
        _connectionFactory = connectionFactory;
        _schemaInitializer = schemaInitializer;
    }

    public async Task<AuthUser?> GetUserByEmailAsync(string email, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetUserByEmailSql(_options.Schema);
        command.Parameters.AddWithValue("email", email);
        return await ReadUserAsync(command, cancellationToken);
    }

    public async Task<AuthUser?> GetUserByIdAsync(Guid userId, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetUserByIdSql(_options.Schema);
        command.Parameters.AddWithValue("id", userId);
        return await ReadUserAsync(command, cancellationToken);
    }

    public async Task<AuthUser> CreateUserAsync(
        string email,
        string? username,
        string passwordHash,
        string role,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildCreateUserSql(_options.Schema);
        command.Parameters.AddWithValue("id", Guid.NewGuid());
        command.Parameters.AddWithValue("email", email);
        command.Parameters.AddWithValue("username", (object?)username ?? DBNull.Value);
        command.Parameters.AddWithValue("password_hash", passwordHash);
        command.Parameters.AddWithValue("role", role);
        command.Parameters.AddWithValue("status", "active");
        command.Parameters.AddWithValue("created_at", DateTimeOffset.UtcNow);
        command.Parameters.AddWithValue("updated_at", DateTimeOffset.UtcNow);

        try
        {
            await using var reader = await command.ExecuteReaderAsync(cancellationToken);
            if (!await reader.ReadAsync(cancellationToken))
            {
                throw new InvalidOperationException("Failed to create auth user.");
            }

            return MapUser(reader);
        }
        catch (PostgresException exception) when (exception.SqlState == PostgresErrorCodes.UniqueViolation)
        {
            throw new InvalidOperationException("User with the same email already exists.", exception);
        }
    }

    public async Task<SessionIssueResult> CreateSessionAsync(
        Guid userId,
        string sessionTokenHash,
        string csrfTokenHash,
        DateTimeOffset createdAt,
        DateTimeOffset expiresAt,
        CancellationToken cancellationToken)
    {
        var sessionId = Guid.NewGuid().ToString("N");

        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildCreateSessionSql(_options.Schema);
        command.Parameters.AddWithValue("id", sessionId);
        command.Parameters.AddWithValue("user_id", userId);
        command.Parameters.AddWithValue("session_token_hash", sessionTokenHash);
        command.Parameters.AddWithValue("csrf_token_hash", csrfTokenHash);
        command.Parameters.AddWithValue("created_at", createdAt);
        command.Parameters.AddWithValue("last_seen_at", createdAt);
        command.Parameters.AddWithValue("expires_at", expiresAt);
        await command.ExecuteNonQueryAsync(cancellationToken);

        return new SessionIssueResult(sessionId, string.Empty, string.Empty, expiresAt);
    }

    public async Task<AuthenticatedSession?> GetAuthenticatedSessionAsync(
        string sessionTokenHash,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetSessionSql(_options.Schema);
        command.Parameters.AddWithValue("session_token_hash", sessionTokenHash);
        command.Parameters.AddWithValue("now", now);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        var user = new AuthUser(
            reader.GetGuid(1),
            reader.GetString(2),
            reader.IsDBNull(3) ? null : reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetString(6),
            reader.GetFieldValue<DateTimeOffset>(7),
            reader.GetFieldValue<DateTimeOffset>(8));
        var sessionId = reader.GetString(0);
        var session = new AuthenticatedSession(
            sessionId,
            user,
            reader.GetFieldValue<DateTimeOffset>(9),
            reader.GetFieldValue<DateTimeOffset>(10),
            []);

        await reader.CloseAsync();
        var capabilities = await GetUserCapabilitiesAsync(connection, user.Id, user.Role, cancellationToken);

        await using var updateCommand = connection.CreateCommand();
        updateCommand.CommandText = AuthSql.BuildUpdateSessionLastSeenSql(_options.Schema);
        updateCommand.Parameters.AddWithValue("id", sessionId);
        updateCommand.Parameters.AddWithValue("last_seen_at", now);
        await updateCommand.ExecuteNonQueryAsync(cancellationToken);

        return session with { Capabilities = capabilities };
    }

    public async Task<bool> ValidateCsrfAsync(string sessionId, string csrfTokenHash, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildValidateCsrfSql(_options.Schema);
        command.Parameters.AddWithValue("id", sessionId);
        command.Parameters.AddWithValue("csrf_token_hash", csrfTokenHash);
        return await command.ExecuteScalarAsync(cancellationToken) is true;
    }

    public async Task RevokeSessionAsync(string sessionId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildRevokeSessionSql(_options.Schema);
        command.Parameters.AddWithValue("id", sessionId);
        command.Parameters.AddWithValue("revoked_at", revokedAt);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task EnsureDevelopmentAdminAsync(
        string email,
        string passwordHash,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildEnsureBootstrapAdminSql(_options.Schema);
        command.Parameters.AddWithValue("id", Guid.NewGuid());
        command.Parameters.AddWithValue("email", email);
        command.Parameters.AddWithValue("password_hash", passwordHash);
        command.Parameters.AddWithValue("created_at", now);
        command.Parameters.AddWithValue("updated_at", now);
        command.Parameters.AddWithValue("role", _options.AdminRole);
        await command.ExecuteNonQueryAsync(cancellationToken);
    }

    public async Task<ServiceClientAuthenticationInfo?> GetServiceClientAuthenticationInfoAsync(
        string clientId,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetServiceClientSql(_options.Schema);
        command.Parameters.AddWithValue("client_id", clientId);
        command.Parameters.AddWithValue("now", now);

        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        if (!await reader.ReadAsync(cancellationToken))
        {
            return null;
        }

        var client = new AuthServiceClient(
            reader.GetGuid(0),
            reader.GetString(1),
            reader.GetString(2),
            reader.GetBoolean(3),
            reader.GetString(4),
            reader.IsDBNull(5) ? null : reader.GetString(5),
            reader.GetFieldValue<DateTimeOffset>(6),
            reader.GetFieldValue<DateTimeOffset>(7));
        await reader.CloseAsync();

        var secrets = await GetServiceClientSecretsAsync(connection, client.Id, now, cancellationToken);
        var capabilities = await GetServiceClientCapabilitiesAsync(connection, client.Id, cancellationToken);

        return new ServiceClientAuthenticationInfo(client, secrets, capabilities);
    }

    private async Task<NpgsqlConnection> OpenConnectionAsync(CancellationToken cancellationToken)
    {
        var connection = await _connectionFactory.OpenConnectionAsync(cancellationToken);
        await _schemaInitializer.EnsureReadyAsync(connection, cancellationToken);
        return connection;
    }

    private async Task<IReadOnlyList<string>> GetUserCapabilitiesAsync(
        NpgsqlConnection connection,
        Guid userId,
        string role,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetUserCapabilitiesSql(_options.Schema);
        command.Parameters.AddWithValue("user_id", userId);
        command.Parameters.AddWithValue("role", role);
        return await ReadCapabilitiesAsync(command, cancellationToken);
    }

    private async Task<IReadOnlyList<string>> GetServiceClientCapabilitiesAsync(
        NpgsqlConnection connection,
        Guid serviceClientId,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetServiceClientCapabilitiesSql(_options.Schema);
        command.Parameters.AddWithValue("service_client_id", serviceClientId);
        return await ReadCapabilitiesAsync(command, cancellationToken);
    }

    private static async Task<IReadOnlyList<string>> ReadCapabilitiesAsync(
        NpgsqlCommand command,
        CancellationToken cancellationToken)
    {
        var capabilities = new List<string>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            capabilities.Add(reader.GetString(0));
        }

        return capabilities;
    }

    private static async Task<AuthUser?> ReadUserAsync(NpgsqlCommand command, CancellationToken cancellationToken)
    {
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        return await reader.ReadAsync(cancellationToken)
            ? MapUser(reader)
            : null;
    }

    private async Task<IReadOnlyList<AuthClientSecret>> GetServiceClientSecretsAsync(
        NpgsqlConnection connection,
        Guid serviceClientId,
        DateTimeOffset now,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = AuthSql.BuildGetServiceClientSecretsSql(_options.Schema);
        command.Parameters.AddWithValue("service_client_id", serviceClientId);
        command.Parameters.AddWithValue("now", now);

        var secrets = new List<AuthClientSecret>();
        await using var reader = await command.ExecuteReaderAsync(cancellationToken);
        while (await reader.ReadAsync(cancellationToken))
        {
            secrets.Add(new AuthClientSecret(
                reader.GetGuid(0),
                reader.GetString(1),
                reader.GetFieldValue<DateTimeOffset>(2),
                reader.IsDBNull(3) ? null : reader.GetFieldValue<DateTimeOffset>(3),
                reader.IsDBNull(4) ? null : reader.GetFieldValue<DateTimeOffset>(4)));
        }

        return secrets;
    }

    private static AuthUser MapUser(NpgsqlDataReader reader)
    {
        return new AuthUser(
            reader.GetGuid(0),
            reader.GetString(1),
            reader.IsDBNull(2) ? null : reader.GetString(2),
            reader.GetString(3),
            reader.GetString(4),
            reader.GetString(5),
            reader.GetFieldValue<DateTimeOffset>(6),
            reader.GetFieldValue<DateTimeOffset>(7));
    }

}
