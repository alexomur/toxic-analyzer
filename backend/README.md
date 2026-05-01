# Backend

`backend/` contains the public ASP.NET Core API for Toxic Analyzer. The backend service exposes stable toxicity-analysis endpoints, validates requests, calls the internal `model` service, returns normalized API responses, and asynchronously captures normalized texts into PostgreSQL for future model training.

## Current Status

- Stack: ASP.NET Core Web API on `net10.0`
- Solution: `backend/ToxicAnalyzer.sln`
- Main entry point: `backend/src/ToxicAnalyzer.Api/Program.cs`
- Public API contract: `backend/API_CONTRACTS.md`
- Internal dependency: Python `model` service over HTTP
- Current runtime model: request processing with optional asynchronous PostgreSQL capture

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
- `POST /api/v1/toxicity/analyze-batch`
- `GET /api/v1/toxicity/texts/random`
- `GET /api/v1/toxicity/texts/{textId}` - stored text, vote counters, and last model snapshot
- `POST /api/v1/toxicity/texts/{textId}/vote`

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

Batch analysis:

- requires non-empty `items`
- preserves input order in the response
- echoes `clientItemId` unchanged
- enforces maximum batch size `100`
- calls `model` endpoint `v1/predict/batch`

Current non-goals in the backend implementation:

- no public auth layer yet
- no public admin or retraining endpoints

## Analysis Capture Storage

When `AnalysisCapture:Enabled` is set, the backend writes analyzed texts into PostgreSQL asynchronously through an in-memory bounded queue and a background worker.

The current storage model intentionally keeps only one row per normalized text in `analysis_texts`:

- deduplication key: SHA-256 fingerprint of the normalized text
- stored text payload: normalized text only
- counters: `request_count`, `votes_toxic`, `votes_non_toxic`
- latest model snapshot: `last_label`, `last_toxic_probability`, `last_model_key`, `last_model_version`
- timestamps: `created_at`, `last_seen_at`

Anonymous voting uses the same table. Random text retrieval prefers rows with fewer total votes through weighted random ordering, while still allowing heavily voted texts to reappear sometimes.

This keeps the database compact and avoids coupling HTTP latency to PostgreSQL writes. Queue overflow or transient database failures can drop capture messages; the public inference response is not blocked by capture.

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

## Verification

From `backend/`:

```powershell
dotnet test .\ToxicAnalyzer.sln
```
