# Internal FastAPI In `model/`

`model/` now contains a thin internal FastAPI layer over the existing Python service-layer.
This API is internal-only: it serves ML runtime and admin scenarios for `backend`, not a public product API.

## Design rules

- FastAPI handlers stay thin and delegate inference to `ToxicityInferenceService`.
- Model weights stay in local artifacts, not in PostgreSQL.
- PostgreSQL is used for training data, `model_registry`, and `retrain_jobs`.
- CLI tools and HTTP handlers reuse the same Python service-layer.

## Entrypoint

From `model/`:

```bash
python -m pip install -e .[dev]
serve-model-api --host 127.0.0.1 --port 8000
```

By default the runtime loads `artifacts/baseline_model_v3_3.pkl`.

## Docker runtime

Build from the repository root:

```bash
docker build -t toxic-analyzer-model:local ./model
```

Run the container:

```bash
docker run --rm -p 8000:8000 --name toxic-analyzer-model toxic-analyzer-model:local
```

Notes:

- The image expects a local model artifact under `model/artifacts/`, typically `baseline_model_v3_3.pkl`.
- `GET /health/live` is suitable for process liveness, while `GET /health/ready` is used as the container healthcheck.
- If retrain or job-status endpoints are needed, pass PostgreSQL settings with `-e TOXIC_ANALYZER_POSTGRES_DSN=...` or the compatible env var set.

## Runtime behavior

### Liveness and readiness

- `GET /health/live` returns success when the process is alive.
- `GET /health/ready` returns success only when an active model is loaded and ready for inference.
- If the local artifact is missing, `live` stays healthy while `ready` returns `503`.

### Active model state

The service keeps a single in-memory active model.

- Successful `reload` swaps the active model without a process restart.
- Failed `reload` does not drop the previously active model.
- All inference responses include `model_key` and `model_version`.

## Endpoints

### Runtime API

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/model/info`
- `POST /v1/predict`
- `POST /v1/predict/batch`

### Admin API

- `POST /v1/admin/reload`
- `POST /v1/admin/retrain`
- `GET /v1/admin/jobs/{job_key}`
- `GET /v1/admin/jobs`

## Inference contract

### Single inference

Request:

```json
{
  "id": "comment-1",
  "text": "ты ведёшь себя как идиот"
}
```

Response:

```json
{
  "id": "comment-1",
  "label": 1,
  "toxic_probability": 0.91,
  "model_key": "baseline-a",
  "model_version": "v3.3"
}
```

### Batch inference

- Batch preserves input order.
- If an item `id` is provided by the client, the same `id` is returned in the corresponding output item.

Request:

```json
{
  "items": [
    { "id": "a", "text": "спокойный комментарий" },
    { "id": "b", "text": "токсичная реплика" }
  ]
}
```

Response:

```json
{
  "model_key": "baseline-a",
  "model_version": "v3.3",
  "items": [
    { "id": "a", "label": 0, "toxic_probability": 0.14 },
    { "id": "b", "label": 1, "toxic_probability": 0.91 }
  ]
}
```

Inference responses now expose only the binary `label` and `toxic_probability`, plus model metadata.

## Reload flow

`POST /v1/admin/reload` supports two modes:

- explicit `model_path`
- `model_key` lookup via `model_registry`

After a successful reload, new inference requests use the newly active model immediately.

## Retrain flow

`POST /v1/admin/retrain` is job-based.

- The HTTP request returns quickly with `job_key`.
- The actual training runs in the background.
- On success the service writes a new local artifact, inserts a row into `model_registry`, and updates `retrain_jobs`.
- The runtime model can then be switched by `reload`.

## PostgreSQL requirements

Retrain and job-status endpoints require configured PostgreSQL access through:

- `TOXIC_ANALYZER_POSTGRES_DSN`
- or the compatible env var set for host, port, db, user, password, sslmode, schema

Inference itself does not require PostgreSQL once the local model artifact is available.
