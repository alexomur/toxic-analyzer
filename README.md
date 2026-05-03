# Toxic Analyzer

Toxic Analyzer is a monorepo for toxicity analysis. The repository contains the public backend API, the frontend SPA, and the internal model service.

## Repository map

- `backend/` - ASP.NET Core backend API
- `frontend/` - React SPA
- `model/` - training pipeline, inference CLI, and internal FastAPI runtime
- `bots/discord/` - Discord bot client for the backend API

## Quick start

Before the first start, make sure the local baseline artifact exists under `model/artifacts/`, typically `model/artifacts/baseline_model_v3_3.pkl`.

```powershell
docker compose up --build
```

This starts:

- `postgres`
- `postgres-init`
- `model`
- `backend`
- `frontend`

To stop the stack:

```powershell
docker compose down
```

To remove PostgreSQL data as well:

```powershell
docker compose down -v
```

## Local endpoints

- frontend: `http://127.0.0.1:3000`
- backend: `http://127.0.0.1:8080`
- OpenAPI in local compose: `http://127.0.0.1:8080/openapi/v1.json`
- Swagger UI in local compose: `http://127.0.0.1:8080/swagger`
- backend health: `http://127.0.0.1:8080/health/live`
- backend readiness: `http://127.0.0.1:8080/health/ready`

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - service boundaries
- [backend/API_CONTRACTS.md](backend/API_CONTRACTS.md) - backend HTTP contracts
- [backend/README.md](backend/README.md) - backend local development
- [frontend/README.md](frontend/README.md) - frontend local development
- [model/README.md](model/README.md) - model development and runtime
