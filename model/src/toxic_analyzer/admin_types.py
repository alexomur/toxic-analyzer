"""Shared types and helpers for model admin flows."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from toxic_analyzer.training_service import BaselineTrainingRequest


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def coerce_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, dict) else {}
    return dict(value)


def coerce_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def close_quietly(resource: Any) -> None:
    close = getattr(resource, "close", None)
    if callable(close):
        close()


@dataclass(slots=True, frozen=True)
class ModelRegistryRecord:
    id: int
    model_key: str
    model_family: str
    model_version: str
    artifact_path: str
    artifact_storage: str
    artifact_sha256: str | None
    training_summary: dict[str, Any]
    metrics: dict[str, Any]
    status: str
    created_at: datetime
    trained_at: datetime | None
    promoted_at: datetime | None


@dataclass(slots=True, frozen=True)
class RetrainJobRecord:
    id: int
    job_key: str
    job_type: str
    trigger_type: str
    status: str
    requested_by: str | None
    output_model_id: int | None
    dataset_snapshot: dict[str, Any]
    job_metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    output_model_key: str | None = None
    output_model_version: str | None = None


@dataclass(slots=True, frozen=True)
class RetrainJobRequest:
    requested_by: str | None = None
    trigger_type: str = "manual"
    training_request: BaselineTrainingRequest = field(default_factory=BaselineTrainingRequest)


class AdminStore(Protocol):
    def create_retrain_job(
        self,
        *,
        job_key: str,
        trigger_type: str,
        requested_by: str | None,
        dataset_snapshot: dict[str, Any],
        job_metadata: dict[str, Any],
    ) -> RetrainJobRecord:
        ...

    def mark_retrain_job_running(self, job_key: str) -> RetrainJobRecord:
        ...

    def mark_retrain_job_succeeded(
        self,
        job_key: str,
        *,
        output_model_id: int,
    ) -> RetrainJobRecord:
        ...

    def mark_retrain_job_failed(self, job_key: str, *, error_message: str) -> RetrainJobRecord:
        ...

    def register_model(
        self,
        *,
        model_key: str,
        model_version: str,
        artifact_path: str,
        artifact_sha256: str,
        training_summary: dict[str, Any],
        metrics: dict[str, Any],
    ) -> ModelRegistryRecord:
        ...

    def get_model(self, model_key: str) -> ModelRegistryRecord | None:
        ...

    def get_retrain_job(self, job_key: str) -> RetrainJobRecord | None:
        ...

    def list_retrain_jobs(self, *, limit: int = 20) -> list[RetrainJobRecord]:
        ...


class BackgroundJobLauncher(Protocol):
    def launch(self, task: Callable[[], None]) -> None:
        ...


class ThreadBackgroundJobLauncher:
    def launch(self, task: Callable[[], None]) -> None:
        thread = threading.Thread(target=task, daemon=True)
        thread.start()
