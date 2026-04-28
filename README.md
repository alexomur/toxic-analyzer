# Toxic Analyzer

Toxic Analyzer is a monorepo for a toxicity-classification project. The repository is currently in the `model-first` stage: active development happens only in `model/`.

## Project scope

- `model/` contains the baseline model, training pipeline, inference CLI, and internal FastAPI runtime.
- `backend/` and `frontend/` are reserved for later stages and should not drive current implementation decisions.
- Notebooks are research-only. Final code must live in regular Python modules.

## Repository map

- `README.md` - project entry point and quick start
- `ARCHITECTURE.md` - target architecture boundaries for future stages
- `model/README.md` - model workspace guide
- `model/MODEL_EVOLUTION.md` - short history of the baseline

## Quick start

The commands below assume Docker is installed and you want to run both PostgreSQL and the model runtime locally.

### 1. Install model dependencies

```powershell
Set-Location .\model
python -m pip install -e .[dev]
```

### 2. Start PostgreSQL for the model pipeline

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

### 3. Initialize the training store

```powershell
apply-training-store-schema --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
$env:TOXIC_ANALYZER_POSTGRES_DSN="postgresql://toxic_model:toxic_model_pw@127.0.0.1:55432/toxic_analyzer_e2e"
```

### 4. Train the baseline model artifact

```powershell
train-baseline --data-source postgres
```

This produces the local artifact used by the runtime, typically `model/artifacts/baseline_model_v3_3.pkl`.

### 5. Build the model container

Run this from the repository root:

```powershell
Set-Location ..
docker build -t toxic-analyzer-model:local .\model
```

### 6. Start the model container

```powershell
docker run --rm -p 8000:8000 `
  --name toxic-analyzer-model `
  -e TOXIC_ANALYZER_POSTGRES_DSN="postgresql://toxic_model:toxic_model_pw@host.docker.internal:55432/toxic_analyzer_e2e" `
  toxic-analyzer-model:local
```

### 7. Verify the runtime

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health/live
Invoke-WebRequest http://127.0.0.1:8000/health/ready
Invoke-WebRequest http://127.0.0.1:8000/v1/model/info
```

## Current rules

- Keep implementation work inside `model/`.
- Do not move product logic into Python service code ahead of time.
- Do not commit datasets, checkpoints, virtual environments, caches, or other local artifacts.

## Where to go next

- For model development: [model/README.md](model/README.md)
- For future service boundaries: [ARCHITECTURE.md](ARCHITECTURE.md)
