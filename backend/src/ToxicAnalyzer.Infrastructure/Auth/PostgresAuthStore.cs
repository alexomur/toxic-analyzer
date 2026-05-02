using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Npgsql;

using ToxicAnalyzer.Application.Auth;

namespace ToxicAnalyzer.Infrastructure.Auth;

public sealed class PostgresAuthStore : IAuthStore
{
    private readonly AuthOptions _options;
    private readonly ILogger<PostgresAuthStore> _logger;
    private bool _schemaEnsured;

    public PostgresAuthStore(
        IOptions<AuthOptions> options,
        ILogger<PostgresAuthStore> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public async Task<AuthUser?> GetUserByEmailAsync(string email, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetUserByEmailSql(_options.Schema);
        command.Parameters.AddWithValue("email", email);
        return await ReadUserAsync(command, cancellationToken);
    }

    public async Task<AuthUser?> GetUserByIdAsync(Guid userId, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetUserByIdSql(_options.Schema);
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
        command.CommandText = BuildCreateUserSql(_options.Schema);
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
        command.CommandText = BuildCreateSessionSql(_options.Schema);
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
        command.CommandText = BuildGetSessionSql(_options.Schema);
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
        updateCommand.CommandText = BuildUpdateSessionLastSeenSql(_options.Schema);
        updateCommand.Parameters.AddWithValue("id", sessionId);
        updateCommand.Parameters.AddWithValue("last_seen_at", now);
        await updateCommand.ExecuteNonQueryAsync(cancellationToken);

        return session with { Capabilities = capabilities };
    }

    public async Task<bool> ValidateCsrfAsync(string sessionId, string csrfTokenHash, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = BuildValidateCsrfSql(_options.Schema);
        command.Parameters.AddWithValue("id", sessionId);
        command.Parameters.AddWithValue("csrf_token_hash", csrfTokenHash);
        return await command.ExecuteScalarAsync(cancellationToken) is true;
    }

    public async Task RevokeSessionAsync(string sessionId, DateTimeOffset revokedAt, CancellationToken cancellationToken)
    {
        await using var connection = await OpenConnectionAsync(cancellationToken);
        await using var command = connection.CreateCommand();
        command.CommandText = BuildRevokeSessionSql(_options.Schema);
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
        command.CommandText = BuildEnsureBootstrapAdminSql(_options.Schema);
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
        command.CommandText = BuildGetServiceClientSql(_options.Schema);
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
        if (string.IsNullOrWhiteSpace(_options.ConnectionString))
        {
            throw new InvalidOperationException("Auth:ConnectionString must be configured.");
        }

        var connection = new NpgsqlConnection(AuthConnectionString.Normalize(_options.ConnectionString));
        await connection.OpenAsync(cancellationToken);

        if (!_schemaEnsured)
        {
            await EnsureSchemaAsync(connection, cancellationToken);
            _schemaEnsured = true;
        }

        return connection;
    }

    private async Task EnsureSchemaAsync(NpgsqlConnection connection, CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = BuildEnsureSchemaSql(_options.Schema);
        command.Parameters.AddWithValue("admin_role", _options.AdminRole);
        await command.ExecuteNonQueryAsync(cancellationToken);
        _logger.LogInformation("Auth schema is ready in PostgreSQL schema {Schema}.", _options.Schema);
    }

    private async Task<IReadOnlyList<string>> GetUserCapabilitiesAsync(
        NpgsqlConnection connection,
        Guid userId,
        string role,
        CancellationToken cancellationToken)
    {
        await using var command = connection.CreateCommand();
        command.CommandText = BuildGetUserCapabilitiesSql(_options.Schema);
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
        command.CommandText = BuildGetServiceClientCapabilitiesSql(_options.Schema);
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
        command.CommandText = BuildGetServiceClientSecretsSql(_options.Schema);
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

    private static string BuildEnsureSchemaSql(string schema) => $$"""
        CREATE SCHEMA IF NOT EXISTS {{schema}};

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_users (
            id UUID PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            username TEXT NULL,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_sessions (
            id TEXT PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES {{schema}}.auth_users (id) ON DELETE CASCADE,
            session_token_hash TEXT NOT NULL UNIQUE,
            csrf_token_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ NULL
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_user_permissions (
            user_id UUID NOT NULL REFERENCES {{schema}}.auth_users (id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, capability)
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_role_permissions (
            role TEXT NOT NULL,
            capability TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (role, capability)
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_service_clients (
            id UUID PRIMARY KEY,
            client_id TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            is_trusted BOOLEAN NOT NULL DEFAULT FALSE,
            status TEXT NOT NULL,
            tenant_id TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_service_client_secrets (
            id UUID PRIMARY KEY,
            service_client_id UUID NOT NULL REFERENCES {{schema}}.auth_service_clients (id) ON DELETE CASCADE,
            secret_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NULL,
            revoked_at TIMESTAMPTZ NULL
        );

        CREATE TABLE IF NOT EXISTS {{schema}}.auth_service_client_permissions (
            service_client_id UUID NOT NULL REFERENCES {{schema}}.auth_service_clients (id) ON DELETE CASCADE,
            capability TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (service_client_id, capability)
        );

        CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
            ON {{schema}}.auth_sessions (session_token_hash);

        CREATE INDEX IF NOT EXISTS idx_auth_service_client_client_id
            ON {{schema}}.auth_service_clients (client_id);

        INSERT INTO {{schema}}.auth_role_permissions (role, capability)
        VALUES
            ('member', 'analysis.read'),
            ('member', 'analysis.vote'),
            (@admin_role, 'analysis.read'),
            (@admin_role, 'analysis.vote'),
            (@admin_role, 'model.reload'),
            (@admin_role, 'model.retrain'),
            (@admin_role, 'dataset.update'),
            (@admin_role, 'admin.users.manage')
        ON CONFLICT (role, capability) DO NOTHING;
        """;

    private static string BuildGetUserByEmailSql(string schema) => $$"""
        SELECT id, email, username, role, password_hash, status, created_at, updated_at
        FROM {{schema}}.auth_users
        WHERE lower(email) = lower(@email);
        """;

    private static string BuildGetUserByIdSql(string schema) => $$"""
        SELECT id, email, username, role, password_hash, status, created_at, updated_at
        FROM {{schema}}.auth_users
        WHERE id = @id;
        """;

    private static string BuildCreateUserSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_users (
            id, email, username, role, password_hash, status, created_at, updated_at
        ) VALUES (
            @id, @email, @username, @role, @password_hash, @status, @created_at, @updated_at
        )
        RETURNING id, email, username, role, password_hash, status, created_at, updated_at;
        """;

    private static string BuildCreateSessionSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_sessions (
            id, user_id, session_token_hash, csrf_token_hash, created_at, last_seen_at, expires_at, revoked_at
        ) VALUES (
            @id, @user_id, @session_token_hash, @csrf_token_hash, @created_at, @last_seen_at, @expires_at, NULL
        );
        """;

    private static string BuildGetSessionSql(string schema) => $$"""
        SELECT
            session.id,
            user_account.id,
            user_account.email,
            user_account.username,
            user_account.role,
            user_account.password_hash,
            user_account.status,
            user_account.created_at,
            user_account.updated_at,
            session.expires_at,
            session.last_seen_at
        FROM {{schema}}.auth_sessions AS session
        INNER JOIN {{schema}}.auth_users AS user_account ON user_account.id = session.user_id
        WHERE session.session_token_hash = @session_token_hash
          AND session.revoked_at IS NULL
          AND session.expires_at > @now
          AND user_account.status = 'active';
        """;

    private static string BuildUpdateSessionLastSeenSql(string schema) => $$"""
        UPDATE {{schema}}.auth_sessions
        SET last_seen_at = @last_seen_at
        WHERE id = @id;
        """;

    private static string BuildValidateCsrfSql(string schema) => $$"""
        SELECT EXISTS (
            SELECT 1
            FROM {{schema}}.auth_sessions
            WHERE id = @id
              AND csrf_token_hash = @csrf_token_hash
              AND revoked_at IS NULL
        );
        """;

    private static string BuildRevokeSessionSql(string schema) => $$"""
        UPDATE {{schema}}.auth_sessions
        SET revoked_at = @revoked_at
        WHERE id = @id;
        """;

    private static string BuildEnsureBootstrapAdminSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_users (
            id, email, username, role, password_hash, status, created_at, updated_at
        ) VALUES (
            @id, @email, NULL, @role, @password_hash, 'active', @created_at, @updated_at
        )
        ON CONFLICT (email) DO NOTHING;
        """;

    private static string BuildGetUserCapabilitiesSql(string schema) => $$"""
        SELECT capability
        FROM (
            SELECT capability
            FROM {{schema}}.auth_role_permissions
            WHERE role = @role

            UNION

            SELECT capability
            FROM {{schema}}.auth_user_permissions
            WHERE user_id = @user_id
        ) AS capabilities
        ORDER BY capability;
        """;

    private static string BuildGetServiceClientSql(string schema) => $$"""
        SELECT id, client_id, display_name, is_trusted, status, tenant_id, created_at, updated_at
        FROM {{schema}}.auth_service_clients
        WHERE client_id = @client_id
          AND status = 'active';
        """;

    private static string BuildGetServiceClientSecretsSql(string schema) => $$"""
        SELECT id, secret_hash, created_at, expires_at, revoked_at
        FROM {{schema}}.auth_service_client_secrets
        WHERE service_client_id = @service_client_id
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > @now)
        ORDER BY created_at DESC;
        """;

    private static string BuildGetServiceClientCapabilitiesSql(string schema) => $$"""
        SELECT capability
        FROM {{schema}}.auth_service_client_permissions
        WHERE service_client_id = @service_client_id
        ORDER BY capability;
        """;
}
