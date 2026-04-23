"""HTTP schemas for the internal FastAPI model service."""


from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LiveHealthResponse(ApiSchema):
    status: Literal["live"] = "live"


class ReadyHealthResponse(ApiSchema):
    status: Literal["ready", "not_ready"]
    detail: str | None = None
    model_key: str | None = None
    model_version: str | None = None


class ModelInfoResponse(ApiSchema):
    model_key: str
    model_version: str
    model_path: str | None
    threshold: float
    calibration_method: str | None
    training_config: dict[str, Any] | None


class PredictRequest(ApiSchema):
    id: str | int | None = None
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank.")
        return value


class PredictionResponse(ApiSchema):
    id: str | int | None = None
    label: int
    toxic_probability: float
    model_key: str
    model_version: str


class BatchPredictionItemRequest(ApiSchema):
    id: str | int | None = None
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not be blank.")
        return value


class BatchPredictionRequest(ApiSchema):
    items: list[BatchPredictionItemRequest] = Field(min_length=1)


class BatchPredictionItemResponse(ApiSchema):
    id: str | int | None = None
    label: int
    toxic_probability: float


class BatchPredictionResponse(ApiSchema):
    model_key: str
    model_version: str
    items: list[BatchPredictionItemResponse]


class ReloadRequest(ApiSchema):
    model_key: str | None = None
    model_path: str | None = None

    @model_validator(mode="after")
    def validate_target(self) -> "ReloadRequest":
        if self.model_key and self.model_path:
            raise ValueError("Specify either model_key or model_path, not both.")
        return self


class ReloadResponse(ApiSchema):
    status: Literal["reloaded"] = "reloaded"
    model_key: str
    model_version: str
    model_path: str | None


class RetrainRequest(ApiSchema):
    requested_by: str | None = None
    trigger_type: Literal["manual", "scheduled", "feedback_threshold", "backfill"] = "manual"
    data_source: Literal["auto", "sqlite", "postgres", "cache"] = "auto"
    dataset_path: str | None = None
    postgres_dsn: str | None = None
    postgres_schema: str | None = None
    dataset_cache_path: str | None = None
    refresh_dataset_cache: bool = False


class RetrainResponse(ApiSchema):
    job_key: str
    status: Literal["queued"]
    trigger_type: str
    requested_by: str | None = None


class JobStatusResponse(ApiSchema):
    job_key: str
    job_type: str
    trigger_type: str
    status: str
    requested_by: str | None
    output_model_id: int | None
    output_model_key: str | None
    output_model_version: str | None
    dataset_snapshot: dict[str, Any]
    job_metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobListResponse(ApiSchema):
    items: list[JobStatusResponse]
