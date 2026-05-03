# Backend

`backend/` contains the ASP.NET Core API for Toxic Analyzer.

## Runtime stack

- ASP.NET Core Web API on `net10.0`
- solution: `backend/ToxicAnalyzer.sln`
- entry point: `backend/src/ToxicAnalyzer.Api/Program.cs`
- internal dependency: Python `model` service over HTTP
- public HTTP contract: [API_CONTRACTS.md](C:/Users/Alexomur/Desktop/projects/toxic-analyzer/backend/API_CONTRACTS.md)

## Solution layout

- `src/ToxicAnalyzer.Api` - HTTP endpoints, OpenAPI, error handling
- `src/ToxicAnalyzer.Application` - application handlers and request validation
- `src/ToxicAnalyzer.Domain` - domain primitives for text and analysis results
- `src/ToxicAnalyzer.Infrastructure` - HTTP client, health checks, and PostgreSQL capture pipeline
- `tests/ToxicAnalyzer.UnitTests` - unit tests for application and infrastructure behavior
- `tests/ToxicAnalyzer.IntegrationTests` - endpoint-level contract tests

## Configuration

Primary settings live in `backend/src/ToxicAnalyzer.Api/appsettings.json`.

- `ModelService:BaseUrl` defaults to `http://localhost:8000/`
- `ModelService:Timeout` defaults to `00:00:10`
- `AnalysisCapture:Enabled` defaults to `false`
- `AnalysisCapture:ConnectionString` is required when capture is enabled
- `AnalysisCapture:Schema` defaults to `public`
- `AnalysisCapture:QueueCapacity` defaults to `4096`
- `AnalysisCapture:BatchSize` defaults to `128`
- `AnalysisCapture:FlushInterval` defaults to `00:00:02`
- `Auth:ConnectionString` is required for browser-session auth and service-client token issuance
- `Auth:Schema` defaults to `public`
- `Auth:TrustedServiceRole` defaults to `trusted_service`
- `Auth:BrowserSessionLifetime` defaults to `7` days
- `Auth:ServiceAccessTokenLifetime` defaults to `15` minutes
- `Auth:BootstrapAdminEmail` and `Auth:BootstrapAdminPassword` are development-only bootstrap credentials

For local `dotnet run`, launch profiles are defined in `backend/src/ToxicAnalyzer.Api/Properties/launchSettings.json`.

Default development URLs:

- `http://localhost:5068`
- `https://localhost:7288`

## Local run

From `backend/`:

```powershell
dotnet restore .\ToxicAnalyzer.sln
dotnet run --project .\src\ToxicAnalyzer.Api\ToxicAnalyzer.Api.csproj
```

This assumes the internal `model` service is reachable at `http://localhost:8000/`, unless `ModelService__BaseUrl` is overridden.

## Docker

The repository-level `docker compose` starts the local stack:

- `postgres`
- `postgres-init`
- `model`
- `backend`

The backend container listens on port `8080`, points to `http://model:8000/`, and enables PostgreSQL-backed analysis capture against the same local `postgres` service.

For local development, the compose file also wires auth storage to the same PostgreSQL instance and bootstraps a default admin account:

- email: `admin@local.test`
- password: `Admin12345!`

Override these values with `BACKEND_BOOTSTRAP_ADMIN_EMAIL` and `BACKEND_BOOTSTRAP_ADMIN_PASSWORD`.

## Auth storage

Auth persistence includes these PostgreSQL tables under `Auth:Schema`:

- `auth_users`
- `auth_sessions`
- `auth_user_permissions`
- `auth_role_permissions`
- `auth_service_clients`
- `auth_service_client_secrets`
- `auth_service_client_permissions`

Default role permissions are seeded for `member` and `admin`. Service clients are first-class subjects with explicit capability grants; `is_trusted` does not imply admin access.

## Swagger auth testing

Swagger UI is available at `/swagger` in development and can exercise the real auth flow.

- browser clients use session cookie auth with CSRF protection
- service clients use bearer tokens from `POST /api/v1/auth/service-token`

Browser-session flow:

1. Call `POST /api/v1/auth/register` or `POST /api/v1/auth/login`.
2. The response sets the `ta_session` cookie and returns `csrfToken` in the response body.
3. Call `GET /api/v1/auth/me` to inspect the active actor and confirm the current `csrfToken`.
4. For session-authenticated write requests such as `POST /api/v1/auth/logout`, paste the `csrfToken` into the `X-CSRF-Token` header parameter shown by Swagger.

Bearer flow:

1. Provision a service client plus at least one hashed secret and explicit capabilities in the auth tables.
2. Call `POST /api/v1/auth/service-token` with `clientId` and `clientSecret`.
3. Use Swagger `Authorize` with the returned bearer token.
4. Call protected bearer-compatible endpoints such as `GET /api/v1/auth/admin-access`.

## Verification

From `backend/`:

```powershell
dotnet test .\ToxicAnalyzer.sln
```
