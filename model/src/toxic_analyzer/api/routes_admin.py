"""Admin FastAPI routes for model reload and retrain orchestration."""

from fastapi import APIRouter, HTTPException, Query, Request, status

from toxic_analyzer.admin_service import RetrainAdminService, RetrainJobRecord, RetrainJobRequest
from toxic_analyzer.api.boundary import AdminApiBoundary
from toxic_analyzer.api.runtime_state import ModelReloadError, ModelRuntimeState
from toxic_analyzer.api.schemas import (
    JobListResponse,
    JobStatusResponse,
    ReloadRequest,
    ReloadResponse,
    RetrainRequest,
    RetrainResponse,
)
from toxic_analyzer.training_service import BaselineTrainingRequest

router = APIRouter()


def _get_runtime_state(request: Request) -> ModelRuntimeState:
    return request.app.state.runtime_state


def _get_admin_service(request: Request) -> RetrainAdminService | None:
    return getattr(request.app.state, "admin_service", None)


def _get_admin_boundary(request: Request) -> AdminApiBoundary:
    return request.app.state.admin_boundary


def _require_admin_service(request: Request) -> RetrainAdminService:
    admin_service = _get_admin_service(request)
    if admin_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Retrain admin service is not configured.",
        )
    return admin_service


def _to_job_status_response(job: RetrainJobRecord) -> JobStatusResponse:
    return JobStatusResponse(
        job_key=job.job_key,
        job_type=job.job_type,
        trigger_type=job.trigger_type,
        status=job.status,
        requested_by=job.requested_by,
        output_model_id=job.output_model_id,
        output_model_key=job.output_model_key,
        output_model_version=job.output_model_version,
        dataset_snapshot=job.dataset_snapshot,
        job_metadata=job.job_metadata,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _build_training_request(request: Request, payload: RetrainRequest) -> BaselineTrainingRequest:
    boundary = _get_admin_boundary(request)
    training_profile = _resolve_training_profile(boundary, payload.training_profile)
    training_request = BaselineTrainingRequest()
    training_request.data_source = training_profile.data_source
    training_request.postgres_dsn = training_profile.postgres_dsn
    training_request.postgres_schema = training_profile.postgres_schema

    if payload.dataset_id is not None:
        training_request.dataset_path = _resolve_dataset_path(boundary, payload.dataset_id)

    if payload.cache_profile is not None:
        cache_profile = _resolve_cache_profile(boundary, payload.cache_profile)
        training_request.dataset_cache_path = cache_profile.dataset_cache_path
        training_request.refresh_dataset_cache = cache_profile.refresh_dataset_cache

    return training_request


@router.post("/v1/admin/reload", response_model=ReloadResponse)
async def reload_model(request: Request, payload: ReloadRequest):
    runtime_state = _get_runtime_state(request)
    target_path = _resolve_model_path(request, payload.model_id)

    try:
        service = runtime_state.reload(target_path)
    except ModelReloadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    identity = service.get_model_identity()
    return ReloadResponse(
        model_key=identity.model_key,
        model_version=identity.model_version,
        model_path=str(service.model_path) if service.model_path is not None else None,
    )


@router.post(
    "/v1/admin/retrain",
    response_model=RetrainResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def retrain_model(request: Request, payload: RetrainRequest):
    admin_service = _require_admin_service(request)
    job = admin_service.start_retrain(
        RetrainJobRequest(
            requested_by=payload.requested_by,
            trigger_type=payload.trigger_type,
            training_request=_build_training_request(request, payload),
        )
    )
    return RetrainResponse(
        job_key=job.job_key,
        status="queued",
        trigger_type=job.trigger_type,
        requested_by=job.requested_by,
    )


@router.get("/v1/admin/jobs/{job_key}", response_model=JobStatusResponse)
async def get_job(request: Request, job_key: str):
    admin_service = _require_admin_service(request)
    job = admin_service.get_retrain_job(job_key)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Retrain job {job_key!r} was not found.",
        )
    return _to_job_status_response(job)


@router.get("/v1/admin/jobs", response_model=JobListResponse)
async def list_jobs(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    admin_service = _require_admin_service(request)
    jobs = admin_service.list_retrain_jobs(limit=limit)
    return JobListResponse(items=[_to_job_status_response(job) for job in jobs])


def _resolve_model_path(request: Request, model_id: str):
    boundary = _get_admin_boundary(request)
    registry_path = None
    admin_service = _get_admin_service(request)
    if admin_service is not None:
        model_record = admin_service.get_model(model_id)
        registry_path = model_record.artifact_path if model_record is not None else None

    try:
        return boundary.resolve_model_path(model_id, registry_path=registry_path)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown model_id {model_id!r}.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _resolve_dataset_path(boundary: AdminApiBoundary, dataset_id: str):
    try:
        return boundary.resolve_dataset_path(dataset_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset_id {dataset_id!r}.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _resolve_cache_profile(boundary: AdminApiBoundary, cache_profile: str):
    try:
        return boundary.resolve_cache_profile(cache_profile)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown cache_profile {cache_profile!r}.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _resolve_training_profile(boundary: AdminApiBoundary, training_profile: str):
    try:
        profile = boundary.resolve_training_profile(training_profile)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown training_profile {training_profile!r}.",
        ) from exc

    if profile.data_source in {"postgres", "cache"} and not profile.postgres_dsn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Training profile {training_profile!r} "
                "is not configured with PostgreSQL access."
            ),
        )

    return profile
