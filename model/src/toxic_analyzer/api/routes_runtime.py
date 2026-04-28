"""Runtime FastAPI routes for model health and inference."""


from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from toxic_analyzer.api.runtime_state import ModelNotReadyError, ModelRuntimeState
from toxic_analyzer.api.schemas import (
    BatchPredictionItemResponse,
    BatchPredictionRequest,
    BatchPredictionResponse,
    ExplainPredictRequest,
    ExplainPredictionResponse,
    LiveHealthResponse,
    ModelInfoResponse,
    PredictionResponse,
    PredictRequest,
    ReadyHealthResponse,
)

router = APIRouter()


def _get_runtime_state(request: Request) -> ModelRuntimeState:
    return request.app.state.runtime_state


def _not_ready_response(detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=ReadyHealthResponse(status="not_ready", detail=detail).model_dump(mode="json"),
    )


@router.get("/health/live", response_model=LiveHealthResponse)
async def health_live() -> LiveHealthResponse:
    return LiveHealthResponse()


@router.get("/health/ready", response_model=ReadyHealthResponse)
async def health_ready(request: Request):
    readiness = _get_runtime_state(request).readiness()
    if not readiness.ready:
        return _not_ready_response(readiness.detail or "Model runtime is not ready.")
    identity = readiness.model_identity
    return ReadyHealthResponse(
        status="ready",
        model_key=identity.model_key if identity is not None else None,
        model_version=identity.model_version if identity is not None else None,
    )


@router.get("/v1/model/info", response_model=ModelInfoResponse)
async def model_info(request: Request):
    runtime_state = _get_runtime_state(request)
    try:
        service = runtime_state.get_service()
    except ModelNotReadyError as exc:
        return _not_ready_response(str(exc))
    info = service.get_model_info()
    identity = service.get_model_identity()
    return ModelInfoResponse(
        model_key=identity.model_key,
        model_version=identity.model_version,
        model_path=info.model_path,
        threshold=info.threshold,
        calibration_method=info.calibration_method,
        training_config=info.training_config,
    )


@router.post("/v1/predict", response_model=PredictionResponse)
async def predict(request: Request, payload: PredictRequest):
    try:
        service = _get_runtime_state(request).get_service()
    except ModelNotReadyError as exc:
        return _not_ready_response(str(exc))
    prediction = service.predict_one(payload.text)
    identity = service.get_model_identity()
    return PredictionResponse(
        id=payload.id,
        label=prediction.label,
        toxic_probability=prediction.toxic_probability,
        model_key=identity.model_key,
        model_version=identity.model_version,
    )


@router.post("/v1/predict/explain", response_model=ExplainPredictionResponse)
async def predict_explained(request: Request, payload: ExplainPredictRequest):
    try:
        service = _get_runtime_state(request).get_service()
    except ModelNotReadyError as exc:
        return _not_ready_response(str(exc))
    prediction = service.predict_one_explained(payload.text, top_n=payload.top_n)
    identity = service.get_model_identity()
    return ExplainPredictionResponse(
        id=payload.id,
        label=prediction.label,
        toxic_probability=prediction.toxic_probability,
        raw_model_probability=prediction.raw_model_probability,
        calibrated_probability=prediction.calibrated_probability,
        posthoc_adjusted_probability=prediction.posthoc_adjusted_probability,
        threshold=prediction.threshold,
        model_key=identity.model_key,
        model_version=identity.model_version,
        explanation=prediction.explanation.to_dict(),
    )


@router.post("/v1/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(request: Request, payload: BatchPredictionRequest):
    try:
        service = _get_runtime_state(request).get_service()
    except ModelNotReadyError as exc:
        return _not_ready_response(str(exc))
    predictions = service.predict_many([item.text for item in payload.items])
    identity = service.get_model_identity()
    items = [
        BatchPredictionItemResponse(
            id=item.id,
            label=prediction.label,
            toxic_probability=prediction.toxic_probability,
        )
        for item, prediction in zip(payload.items, predictions, strict=True)
    ]
    return BatchPredictionResponse(
        model_key=identity.model_key,
        model_version=identity.model_version,
        items=items,
    )
