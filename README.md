# Toxic Analyzer

Toxic Analyzer is a monorepo for a toxicity-classification project. The baseline model is considered ready, and active development is now centered on `backend/`.

## Project scope

- `backend/` contains the product API that will integrate with the internal model service.
- `model/` contains the trained baseline, training pipeline, inference CLI, and internal FastAPI runtime.
- `frontend/` remains a later stage and should follow stable backend contracts.
- Notebooks remain research-only. Final model code must live in regular Python modules.

## Repository map

- `README.md` - project entry point and quick start
- `ARCHITECTURE.md` - service boundaries and integration contract
- `backend/README.md` - backend workspace guide
- `model/README.md` - model workspace guide
- `model/MODEL_EVOLUTION.md` - short history of the baseline

## Quick start

The repository now has two practical entry points: `backend/` for product API development and `model/` for the internal ML runtime.

### Backend

```powershell
Set-Location .\backend
dotnet restore .\ToxicAnalyzer.sln
dotnet run --project .\ToxicAnalyzer.Api\ToxicAnalyzer.Api.csproj
```

The current backend project is an ASP.NET Core API skeleton with Swagger enabled in development.

### Model runtime

The commands below assume Docker is installed and you want to run PostgreSQL and the internal model runtime locally.

#### 1. Install model dependencies

```powershell
Set-Location .\model
python -m pip install -e .[dev]
```

#### 2. Start PostgreSQL for the model pipeline

```powershell
docker volume create toxic-analyzer-postgres-e2e-data
docker run -d `
  --name toxic-analyzer-postgres-e2e `
  -e POSTGRES_DB=toxic_analyzer_e2e `
  -e POSTGRES_USER=toxic_model `
  -e POSTGRES_PASSWORD=toxic_model_pw `
  -p 127.0.0.1:55432:5432 `
  --health-cmd "pg_isready -U toxic_model -d toxic_analyzer_e2e" `
  --health-interval 5s `
  --health-timeout 3s `
  --health-retries 20 `
  -v toxic-analyzer-postgres-e2e-data:/var/lib/postgresql/data `
  postgres:17
```

#### 3. Initialize the training store

```powershell
apply-training-store-schema --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
$env:TOXIC_ANALYZER_POSTGRES_DSN="postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
```

#### 4. Train the baseline model artifact

```powershell
train-baseline --data-source postgres
```

This produces the local artifact used by the runtime, typically `model/artifacts/baseline_model_v3_3.pkl`.

#### 5. Build the model container

Run this from the repository root:

```powershell
Set-Location ..
docker build -t toxic-analyzer-model:local .\model
```

#### 6. Start the model container

```powershell
docker run --rm -p 8000:8000 `
  --name toxic-analyzer-model `
  -e TOXIC_ANALYZER_POSTGRES_DSN="postgresql://toxic_model:toxic_model_pw@host.docker.internal:55432/toxic_analyzer_e2e" `
  toxic-analyzer-model:local
```

#### 7. Verify the runtime

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health/live
Invoke-WebRequest http://127.0.0.1:8000/health/ready
Invoke-WebRequest http://127.0.0.1:8000/v1/model/info
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
