# Architecture

This document describes the current service boundaries after backend MVP completion. It remains a boundary document, not a full delivery checklist.

## Current reality

- The baseline model in `model/` is treated as ready for integration.
- Backend MVP in `backend/` is complete and now defines the public API boundary.
- `frontend/` remains the next stage and should integrate against backend contracts.
- The next backend work should be driven by frontend integration needs, not by expanding `model/`.

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

Current product backend and public API boundary.

Responsibilities:

- public API for the frontend
- orchestration, authorization, and product logic
- storing feedback and product data
- calling the internal `model` service
- assigning product-level semantics to analyzed texts, voting flows, and actor permissions

Current implementation note:

- the repository contains a layered ASP.NET Core backend in `backend/src/`
- MVP endpoints are implemented in `backend/src/ToxicAnalyzer.Api`
- backend delegates inference to `model` and asynchronously captures normalized analyzed texts into PostgreSQL for future product feedback and training workflows

### `frontend`

Future user interface. It should communicate with `backend`, not directly with `model`.

Near-term frontend responsibilities:

- browser login, registration, logout, and current-session restore
- single-text analysis with explainability
- batch analysis with client-side charts and derived analytics
- random-text retrieval and voting
- authenticated text lookup by `textId`

Frontend non-goals for MVP:

- direct `model` integration
- user history screens
- admin interfaces

## Frontend MVP contract decisions

- Browser auth uses backend-managed HttpOnly cookie sessions with CSRF protection.
- Self-registration is part of MVP and should remain simple, with room for later hardening.
- Single-text analysis in the frontend should always request `reportLevel=full`.
- Batch analysis in the frontend should always use the batch endpoint and render analytics client-side.
- `GET /api/v1/toxicity/texts/{textId}` is product data and should require authentication.
- Voting should stay unified around backend-owned `textId` resources instead of frontend-owned ad hoc text payloads.

## Voteable text model

The project should treat voteable texts as backend-owned entities with explicit origin metadata.

Required origin categories for near-term backend work:

- `random_pool`
- `self_submitted`
- `bot_submitted`

Implications:

- random voting continues to use stored candidate texts
- analyzing a user's own text may create or reuse a voteable text entity and return its `textId`
- future bots should reuse the same backend text and vote model instead of introducing a parallel flow
- repeated votes may stay allowed in MVP, but they should be modeled as feedback events, not as a unique final user state

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
- Backend now persists deduplicated analyzed texts as product data in PostgreSQL; model-specific training and registry data remain separate concerns in the same database.
- Product feedback data should remain in backend-owned tables and contracts even when it later feeds model retraining workflows.

## Deployment boundary

- The system should support both same-origin and cross-origin frontend deployment.
- Same-origin remains the simplest local and small-server deployment model.
- Cross-origin support should be treated as a first-class backend concern through explicit CORS configuration and stable session/CSRF behavior.
- Frontend deployment decisions must not leak product logic or auth decisions into `model`.

## Near-term direction

- Build the next backend capabilities around the existing model contract instead of expanding product logic inside `model`.
- Keep the model runtime thin and reusable from both CLI and HTTP.
- Use the completed backend MVP contracts as the integration baseline for frontend work.
- Complete the backend refactor needed for authenticated text lookup, voteable text origins, and deploy-ready browser integration before starting substantive frontend implementation.
