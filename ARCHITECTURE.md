# Planned Architecture

This document describes the target architecture of the project. It is a boundary document, not an implementation checklist for the current `model-first` stage.

## Current reality

- Active development is limited to `model/`.
- `backend/` and `frontend/` are placeholders for future work.
- The current goal is a reproducible baseline model with a narrow internal runtime.

## Planned services

### `model`

Internal Python service around the toxicity model.

Responsibilities:

- load local model artifacts
- run single and batch inference
- expose internal admin operations such as `reload` and `retrain`
- own training and retraining pipelines

Out of scope:

- public product API
- user-facing business logic
- feedback storage as product behavior
- frontend-facing analytics

### `backend`

Future product backend.

Responsibilities:

- public API for the frontend
- orchestration, authorization, and product logic
- storing feedback and product data
- calling the internal `model` service

### `frontend`

Future user interface. It should communicate with `backend`, not directly with `model`.

## Internal contract between `backend` and `model`

The `model` service should stay narrow and predictable.

Expected runtime operations:

- `GET /health/live`
- `GET /health/ready`
- `GET /v1/model/info`
- `POST /v1/predict`
- `POST /v1/predict/explain`
- `POST /v1/predict/batch`

Expected admin operations:

- `POST /v1/admin/reload`
- `POST /v1/admin/retrain`
- `GET /v1/admin/jobs/{job_key}`
- `GET /v1/admin/jobs`

Inference responses should expose:

- binary `label`
- `toxic_probability`
- `model_key`
- `model_version`

The explain operation should additionally expose:

- calibrated and posthoc-adjusted probabilities
- active threshold
- feature-level explanation details

## Data boundaries

- Model weights stay in local artifacts under `model/`.
- PostgreSQL is the shared store for training texts, curated candidates, feedback-derived data, model registry metadata, and retrain jobs.
- PostgreSQL is not the storage for binary model weights.

## Near-term direction

- Keep the model runtime thin.
- Reuse the same Python service layer from both CLI and HTTP.
- Prepare `model/` for PostgreSQL-backed training without pulling product concerns into it.
