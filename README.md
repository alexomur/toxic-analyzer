# Toxic Analyzer

Toxic Analyzer is a monorepo for a toxicity-classification project. The baseline model is integrated as an internal service, and the backend in `backend/` now captures deduplicated analyzed texts into PostgreSQL for future feedback and training workflows.

## Project scope

- `backend/` contains the public product API, integrates with the internal model service, and asynchronously stores deduplicated analyzed texts in PostgreSQL.
- `model/` contains the trained baseline, training pipeline, inference CLI, and internal FastAPI runtime.
- `frontend/` remains the next stage and should consume the stable backend contracts.
- Notebooks remain research-only. Final model code must live in regular Python modules.

## Repository map

- `README.md` - project entry point and quick start
- `ARCHITECTURE.md` - service boundaries and integration contract
- `backend/README.md` - backend workspace guide
- `model/README.md` - model workspace guide
- `model/MODEL_EVOLUTION.md` - short history of the baseline

## Quick start

The local stack is now intended to run through `docker compose` from the repository root.

### Full application stack

Before the first start, make sure the local baseline artifact exists under `model/artifacts/`, typically `model/artifacts/baseline_model_v3_3.pkl`.

```powershell
docker compose up --build
```

What starts:

- `postgres` as the shared training/admin/product-data store
- `postgres-init` as a one-shot schema initializer
- `model` as the internal FastAPI runtime
- `backend` as the public ASP.NET Core API with asynchronous analysis capture enabled

Primary local endpoint:

- backend: `http://127.0.0.1:8080`
- OpenAPI in local compose: `http://127.0.0.1:8080/openapi/v1.json`
- Swagger UI in local compose: `http://127.0.0.1:8080/swagger`
- backend health: `http://127.0.0.1:8080/health/live`
- backend readiness: `http://127.0.0.1:8080/health/ready`

To stop the stack:

```powershell
docker compose down
```

To remove PostgreSQL data as well:

```powershell
docker compose down -v
```

### Backend without containers

```powershell
Set-Location .\backend
dotnet restore .\ToxicAnalyzer.sln
dotnet run --project .\src\ToxicAnalyzer.Api\ToxicAnalyzer.Api.csproj
```

For non-container local backend development, the default model base URL remains `http://localhost:8000/`. Swagger UI is enabled when `ASPNETCORE_ENVIRONMENT=Development`.

Implemented public backend endpoints:

- `POST /api/v1/toxicity/analyze`
- `POST /api/v1/toxicity/analyze-batch`

### Model runtime without compose

```powershell
Set-Location .\model
python -m pip install -e .[dev]
serve-model-api --host 127.0.0.1 --port 8000
```

## Current rules

- Keep product API work inside `backend/`.
- Keep ML-specific implementation and artifacts inside `model/`.
- Do not move product logic into the Python model service.
- Do not commit datasets, checkpoints, virtual environments, caches, or other local artifacts.

## Where to go next

- For backend development: [backend/README.md](backend/README.md)
- For model runtime details: [model/README.md](model/README.md)
- For service boundaries: [ARCHITECTURE.md](ARCHITECTURE.md)
- For backend HTTP contracts: [backend/API_CONTRACTS.md](backend/API_CONTRACTS.md)
