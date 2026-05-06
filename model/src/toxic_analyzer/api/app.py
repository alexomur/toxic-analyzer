"""FastAPI entrypoint for the internal model runtime service."""


import argparse
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from toxic_analyzer.admin_service import RetrainAdminService
from toxic_analyzer.api.boundary import (
    AdminApiBoundary,
    InternalAuthOptions,
    load_admin_api_boundary_from_env,
    load_internal_auth_options_from_env,
)
from toxic_analyzer.api.routes_admin import router as admin_router
from toxic_analyzer.api.routes_runtime import router as runtime_router
from toxic_analyzer.api.runtime_state import ModelRuntimeState
from toxic_analyzer.model_runtime import DEFAULT_MODEL_PATH
from toxic_analyzer.postgres_store import ConnectionFactory, resolve_postgres_settings

MAX_REQUEST_BODY_BYTES = 1_048_576


def create_app(
    *,
    runtime_state: ModelRuntimeState | None = None,
    admin_service: RetrainAdminService | None = None,
    default_model_path: Path = DEFAULT_MODEL_PATH,
    postgres_dsn: str | None = None,
    postgres_schema: str | None = None,
    connection_factory: ConnectionFactory | None = None,
    internal_auth: InternalAuthOptions | None = None,
    admin_boundary: AdminApiBoundary | None = None,
) -> FastAPI:
    resolved_internal_auth = internal_auth or load_internal_auth_options_from_env()
    resolved_admin_boundary = admin_boundary or load_admin_api_boundary_from_env(
        postgres_dsn=postgres_dsn,
        postgres_schema=postgres_schema,
    )
    resolved_runtime_state = runtime_state or ModelRuntimeState(
        default_model_path=default_model_path,
        allowed_artifacts_root=resolved_admin_boundary.artifacts_root,
    )
    resolved_admin_service = admin_service
    if resolved_admin_service is None:
        postgres_settings = resolve_postgres_settings(
            dsn=postgres_dsn,
            schema=postgres_schema,
            require=False,
        )
        if postgres_settings is not None:
            resolved_admin_service = RetrainAdminService.from_postgres_settings(
                postgres_settings,
                connection_factory=connection_factory,
            )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime_state = resolved_runtime_state
        app.state.admin_service = resolved_admin_service
        app.state.internal_auth = resolved_internal_auth
        app.state.admin_boundary = resolved_admin_boundary
        resolved_runtime_state.initialize()
        yield

    app = FastAPI(
        title="Toxic Analyzer Model API",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def enforce_request_size_limit(request, call_next):
        if request.headers.get("content-length"):
            content_length = int(request.headers["content-length"])
            if content_length > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"Request body must not exceed {MAX_REQUEST_BODY_BYTES} bytes."
                    },
                )

        return await call_next(request)

    @app.middleware("http")
    async def enforce_internal_auth(request, call_next):
        if (
            not resolved_internal_auth.enabled
            or request.url.path in {"/health/live", "/health/ready"}
        ):
            return await call_next(request)

        provided_key = request.headers.get(resolved_internal_auth.header_name)
        if provided_key != resolved_internal_auth.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Internal authentication required."},
            )

        return await call_next(request)

    app.include_router(runtime_router)
    if resolved_admin_boundary.enabled:
        app.include_router(admin_router)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--postgres-dsn")
    parser.add_argument("--postgres-schema")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "Running the FastAPI layer requires `uvicorn`. Install model dependencies with "
            "`python -m pip install -e .[dev]` inside `model/`."
        ) from exc

    uvicorn.run(
        create_app(
            default_model_path=args.model_path.resolve(),
            postgres_dsn=args.postgres_dsn,
            postgres_schema=args.postgres_schema,
        ),
        host=args.host,
        port=int(args.port),
    )
