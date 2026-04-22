"""Admin FastAPI routes for model reload and retrain orchestration."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status

from toxic_analyzer.admin_service import RetrainAdminService, RetrainJobRecord, RetrainJobRequest
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


def _build_training_request(payload: RetrainRequest) -> BaselineTrainingRequest:
    training_request = BaselineTrainingRequest()
    if payload.data_source is not None:
        training_request.data_source = payload.data_source
    if payload.dataset_path is not None:
        training_request.dataset_path = Path(payload.dataset_path).resolve()
    if payload.postgres_dsn is not None:
        training_request.postgres_dsn = payload.postgres_dsn
    if payload.postgres_schema is not None:
        training_request.postgres_schema = payload.postgres_schema
    if payload.dataset_cache_path is not None:
        training_request.dataset_cache_path = Path(payload.dataset_cache_path).resolve()
    training_request.refresh_dataset_cache = payload.refresh_dataset_cache
    return training_request


@router.post("/v1/admin/reload", response_model=ReloadResponse)
async def reload_model(request: Request, payload: ReloadRequest):
    runtime_state = _get_runtime_state(request)
    target_path: Path | None = None

    if payload.model_key is not None:
        admin_service = _require_admin_service(request)
        model_record = admin_service.get_model(payload.model_key)
        if model_record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model {payload.model_key!r} was not found in model_registry.",
            )
        target_path = Path(model_record.artifact_path)
    elif payload.model_path is not None:
        target_path = Path(payload.model_path)

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
            training_request=_build_training_request(payload),
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
