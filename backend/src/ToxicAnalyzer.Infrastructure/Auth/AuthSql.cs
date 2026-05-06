namespace ToxicAnalyzer.Infrastructure.Auth;

internal static class AuthSql
{
    public static string BuildEnsureSchemaSql(string schema) => $$"""
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
            (@admin_role, 'analysis.submit'),
            (@admin_role, 'model.reload'),
            (@admin_role, 'model.retrain'),
            (@admin_role, 'dataset.update'),
            (@admin_role, 'admin.users.manage')
        ON CONFLICT (role, capability) DO NOTHING;
        """;

    public static string BuildGetUserByEmailSql(string schema) => $$"""
        SELECT id, email, username, role, password_hash, status, created_at, updated_at
        FROM {{schema}}.auth_users
        WHERE lower(email) = lower(@email);
        """;

    public static string BuildGetUserByIdSql(string schema) => $$"""
        SELECT id, email, username, role, password_hash, status, created_at, updated_at
        FROM {{schema}}.auth_users
        WHERE id = @id;
        """;

    public static string BuildCreateUserSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_users (
            id, email, username, role, password_hash, status, created_at, updated_at
        ) VALUES (
            @id, @email, @username, @role, @password_hash, @status, @created_at, @updated_at
        )
        RETURNING id, email, username, role, password_hash, status, created_at, updated_at;
        """;

    public static string BuildCreateSessionSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_sessions (
            id, user_id, session_token_hash, csrf_token_hash, created_at, last_seen_at, expires_at, revoked_at
        ) VALUES (
            @id, @user_id, @session_token_hash, @csrf_token_hash, @created_at, @last_seen_at, @expires_at, NULL
        );
        """;

    public static string BuildGetSessionSql(string schema) => $$"""
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

    public static string BuildUpdateSessionLastSeenSql(string schema) => $$"""
        UPDATE {{schema}}.auth_sessions
        SET last_seen_at = @last_seen_at
        WHERE id = @id;
        """;

    public static string BuildValidateCsrfSql(string schema) => $$"""
        SELECT EXISTS (
            SELECT 1
            FROM {{schema}}.auth_sessions
            WHERE id = @id
              AND csrf_token_hash = @csrf_token_hash
              AND revoked_at IS NULL
        );
        """;

    public static string BuildRevokeSessionSql(string schema) => $$"""
        UPDATE {{schema}}.auth_sessions
        SET revoked_at = @revoked_at
        WHERE id = @id;
        """;

    public static string BuildEnsureBootstrapAdminSql(string schema) => $$"""
        INSERT INTO {{schema}}.auth_users (
            id, email, username, role, password_hash, status, created_at, updated_at
        ) VALUES (
            @id, @email, NULL, @role, @password_hash, 'active', @created_at, @updated_at
        )
        ON CONFLICT (email) DO NOTHING;
        """;

    public static string BuildGetUserCapabilitiesSql(string schema) => $$"""
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

    public static string BuildGetServiceClientSql(string schema) => $$"""
        SELECT id, client_id, display_name, is_trusted, status, tenant_id, created_at, updated_at
        FROM {{schema}}.auth_service_clients
        WHERE client_id = @client_id
          AND status = 'active';
        """;

    public static string BuildGetServiceClientSecretsSql(string schema) => $$"""
        SELECT id, secret_hash, created_at, expires_at, revoked_at
        FROM {{schema}}.auth_service_client_secrets
        WHERE service_client_id = @service_client_id
          AND revoked_at IS NULL
          AND (expires_at IS NULL OR expires_at > @now)
        ORDER BY created_at DESC;
        """;

    public static string BuildGetServiceClientCapabilitiesSql(string schema) => $$"""
        SELECT capability
        FROM {{schema}}.auth_service_client_permissions
        WHERE service_client_id = @service_client_id
        ORDER BY capability;
        """;
}
