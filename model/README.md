# Model Workspace

`model/` is the only active implementation area of the repository. Its job is to produce and serve the baseline toxicity model.

## Boundaries

- Use notebooks only for research.
- Keep final code in `src/`.
- Keep training, evaluation, inference CLI, and the internal runtime inside `model/`.
- Do not expand this workspace into product `backend` or `frontend`.

## Directory map

- `src/` - Python package and CLI/runtime code
- `tests/` - automated tests
- `configs/` - model and data pipeline configs
- `sql/postgres/` - training store schema
- `notebooks/` - research only
- `data/` - local datasets, not for git
- `artifacts/` - trained models and reports, not for git

## Setup

Recommended Python version: `3.12`.

```powershell
python -m pip install -e .[dev]
```

## Daily commands

### Train baseline

```powershell
train-baseline --data-source auto
```

`auto` prefers PostgreSQL when `TOXIC_ANALYZER_POSTGRES_DSN` is configured and falls back to the legacy SQLite dataset otherwise.

### Predict one text

```powershell
predict-baseline --text "ты ведешь себя как идиот"
```

### Interactive CLI

```powershell
ask-baseline
```

## PostgreSQL training store

Initialize schema:

```powershell
apply-training-store-schema --postgres-dsn "postgresql://user:pass@host:5432/toxic_analyzer"
```

Import the legacy mixed dataset:

```powershell
import-mixed-dataset-to-postgres --postgres-dsn "postgresql://user:pass@host:5432/toxic_analyzer"
```

Set DSN for repeated commands:

```powershell
$env:TOXIC_ANALYZER_POSTGRES_DSN="postgresql://user:pass@host:5432/toxic_analyzer"
```

## Runtime API

Start the internal FastAPI runtime from `model/`:

```powershell
serve-model-api --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/model/info`
- `POST /v1/predict`
- `POST /v1/predict/explain`
- `POST /v1/predict/batch`
- `POST /v1/admin/reload`
- `POST /v1/admin/retrain`
- `GET /v1/admin/jobs/{job_key}`
- `GET /v1/admin/jobs`

Notes:

- Inference endpoints require a local model artifact.
- `POST /v1/predict/explain` returns the prediction plus feature-level explanation fields.
- Admin endpoints are available only when the app is started with PostgreSQL settings that allow `RetrainAdminService` to be configured.
- Retrain and job-status endpoints additionally require PostgreSQL access.

## Docker runtime

Build from the repository root:

```powershell
docker build -t toxic-analyzer-model:local .\model
```

Run the container:

```powershell
docker run --rm -p 8000:8000 `
  --name toxic-analyzer-model `
  -e TOXIC_ANALYZER_POSTGRES_DSN="postgresql://user:pass@host.docker.internal:5432/toxic_analyzer" `
  toxic-analyzer-model:local
```

The image copies `model/artifacts/` during build, so create or refresh the artifact before building the image.

## Working definition of toxicity

For the current baseline, a text is toxic when it contains directed verbal aggression toward a person or group, for example:

- insults or humiliation
- threats or wishes of harm
- hostile generalizations about a group
- aggressive imperative or dismissive attacks aimed at the addressee

Usually not toxic on this stage:

- disagreement without personal attack
- criticism of an idea, product, or event
- negative emotion without a target
- quotation of toxic text without endorsing it

When the case is ambiguous, prefer the more conservative interpretation unless directed aggression is clear.

## Related docs

- Project entry point: [README.md](../README.md)
- Planned boundaries: [ARCHITECTURE.md](../ARCHITECTURE.md)
- Baseline history: [MODEL_EVOLUTION.md](MODEL_EVOLUTION.md)
