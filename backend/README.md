# Backend

`backend/` contains the public ASP.NET Core API for Toxic Analyzer. The backend service exposes stable toxicity-analysis endpoints, validates requests, calls the internal `model` service, returns normalized API responses, and asynchronously captures normalized texts into PostgreSQL for future model training.

## Current Status

- Stack: ASP.NET Core Web API on `net10.0`
- Solution: `backend/ToxicAnalyzer.sln`
- Main entry point: `backend/src/ToxicAnalyzer.Api/Program.cs`
- Public API contract: `backend/API_CONTRACTS.md`
- Internal dependency: Python `model` service over HTTP
- Current runtime model: request processing with optional asynchronous PostgreSQL capture
- Next required refactor: frontend-ready auth, voteable-text semantics, and deploy-ready browser integration

## Solution Layout

- `src/ToxicAnalyzer.Api` - HTTP endpoints, OpenAPI, error handling
- `src/ToxicAnalyzer.Application` - application handlers and request validation
- `src/ToxicAnalyzer.Domain` - domain primitives for text and analysis results
- `src/ToxicAnalyzer.Infrastructure` - HTTP client, health checks, and PostgreSQL capture pipeline
- `tests/ToxicAnalyzer.UnitTests` - unit tests for application and infrastructure behavior
- `tests/ToxicAnalyzer.IntegrationTests` - endpoint-level contract tests

## Implemented Public API

The backend currently exposes these public endpoints:

- `POST /api/v1/toxicity/analyze`
- `POST /api/v1/toxicity/analyze-batch` - requires authentication
- `GET /api/v1/toxicity/texts/random` - requires authentication
- `GET /api/v1/toxicity/texts/{textId}` - stored text, vote counters, and last model snapshot
- `POST /api/v1/toxicity/texts/{textId}/vote` - requires authentication
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/service-token`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/admin-access` - capability check for `admin.users.manage`

Supporting endpoints:

- `GET /health/live`
- `GET /health/ready`

In development, the service also exposes:

- OpenAPI JSON at `/openapi/v1.json`
- Swagger UI at `/swagger`

## Current Behavior

Single-text analysis:

- requires `text`
- accepts optional `reportLevel` with values `summary` or `full`
- defaults `reportLevel` to `summary`
- calls `model` endpoint `v1/predict` for `summary`
- calls `model` endpoint `v1/predict/explain` for `full`
- frontend MVP should always call this flow with `reportLevel=full`

Batch analysis:

- requires authentication
- requires non-empty `items`
- preserves input order in the response
- echoes `clientItemId` unchanged
- enforces maximum batch size `100`
- calls `model` endpoint `v1/predict/batch`
- frontend MVP should render charts and derived analytics client-side from this response

Current non-goals in the backend implementation:

- no public retraining endpoints yet

## Analysis Capture Storage

When `AnalysisCapture:Enabled` is set, the backend writes analyzed texts into PostgreSQL asynchronously through an in-memory bounded queue and a background worker.

The current storage model intentionally keeps only one row per normalized text in `analysis_texts`:

- deduplication key: SHA-256 fingerprint of the normalized text
- stored text payload: normalized text only
- counters: `request_count`, `votes_toxic`, `votes_non_toxic`
- latest model snapshot: `last_label`, `last_toxic_probability`, `last_model_key`, `last_model_version`
- timestamps: `created_at`, `last_seen_at`

Authenticated voting uses the same table. Random text retrieval prefers rows with fewer total votes through weighted random ordering, while still allowing heavily voted texts to reappear sometimes.

This keeps the database compact and avoids coupling HTTP latency to PostgreSQL writes. Queue overflow or transient database failures can drop capture messages; the public inference response is not blocked by capture.

## Frontend Integration Decisions

- browser users use cookie-session auth with CSRF protection
- self-registration is part of MVP
- batch analysis and text-labeling flows require authentication both in the browser UI and at the API layer
- `GET /api/v1/toxicity/texts/{textId}` should be treated as authenticated product data
- single-text analysis is an explainability flow
- batch analysis is a client-side analytics flow
- user-facing history is out of scope for MVP

## Voteable Text Direction

Before substantive frontend work, the backend should move from a generic captured-text model to a voteable-text model with explicit origin semantics.

Near-term origin categories:

- `random_pool`
- `self_submitted`
- `bot_submitted`

The intended direction is:

- keep voting centered on backend-issued `textId`
- allow voting both for random texts and for a user's own analyzed text
- keep future bot flows on the same backend contract
- treat repeated votes as allowed feedback events in MVP instead of enforcing uniqueness now

## Error Handling

The API uses ASP.NET Core `ProblemDetails`.

Current status mapping:

- `400` for request validation errors
- `503` when the `model` service is unavailable or returns an invalid upstream response
- `504` when the `model` service times out
- `500` for unexpected backend failures

Validation responses include `errors` with `{ field, message }` items.

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
- frontend deployment should also introduce explicit allowed-origin configuration for browser clients when the UI is served from a different origin

For local `dotnet run`, launch profiles are defined in `backend/src/ToxicAnalyzer.Api/Properties/launchSettings.json`.

Default development URLs:

- `http://localhost:5068`
- `https://localhost:7288`

## Local Run

From `backend/`:

```powershell
dotnet restore .\ToxicAnalyzer.sln
dotnet run --project .\src\ToxicAnalyzer.Api\ToxicAnalyzer.Api.csproj
```

This assumes the internal `model` service is reachable at `http://localhost:8000/`, unless `ModelService__BaseUrl` is overridden.

## Docker

The repository-level `docker compose` starts the intended local stack:

- `postgres`
- `postgres-init`
- `model`
- `backend`

The backend container listens on port `8080`, points to `http://model:8000/`, and enables PostgreSQL-backed analysis capture against the same local `postgres` service.

For local development, the compose file also wires auth storage to the same PostgreSQL instance and bootstraps a default admin account:

- email: `admin@local.test`
- password: `Admin12345!`

Override these values with `BACKEND_BOOTSTRAP_ADMIN_EMAIL` and `BACKEND_BOOTSTRAP_ADMIN_PASSWORD`.

## Auth Architecture

The backend now uses a split auth model:

- browser/frontend users authenticate with HttpOnly cookie sessions and CSRF protection
- bots and services authenticate with client credentials and receive short-lived bearer JWT access tokens from the backend
- authorization is capability-based, with the current foundation including `analysis.read`, `analysis.vote`, `model.reload`, `model.retrain`, `dataset.update`, and `admin.users.manage`

Near-term expectation:

- frontend should primarily use the browser-session flow
- bot integrations should continue to use service-token flow
- backend deployment should remain compatible with both same-origin and cross-origin frontend hosting

Layering is intentionally separated:

- `ToxicAnalyzer.Api` keeps HTTP endpoints, auth handlers, cookie serialization, CSRF middleware, and policy wiring
- `ToxicAnalyzer.Application` owns auth use cases, auth abstractions, and actor/capability contracts
- `ToxicAnalyzer.Infrastructure` owns PostgreSQL auth persistence, service-client storage, JWT issuance, and development bootstrap persistence

## Auth Storage

Auth persistence now includes these PostgreSQL tables under `Auth:Schema`:

- `auth_users`
- `auth_sessions`
- `auth_user_permissions`
- `auth_role_permissions`
- `auth_service_clients`
- `auth_service_client_secrets`
- `auth_service_client_permissions`

Default role permissions are seeded for `member` and `admin`. Service clients are first-class subjects with explicit capability grants; `is_trusted` does not imply admin access.

## Swagger Auth Testing

Swagger UI is available at `/swagger` in development and can exercise the real auth flow without special dev-only endpoints.

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
