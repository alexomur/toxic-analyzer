"""Shared in-memory runtime state for the FastAPI model service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable

from toxic_analyzer.inference_service import ModelIdentity, ToxicityInferenceService
from toxic_analyzer.model_runtime import (
    DEFAULT_ARTIFACT_PATHS,
    DEFAULT_MODEL_PATH,
    ModelArtifactPaths,
    build_missing_model_message,
)

RuntimeServiceLoader = Callable[[Path], ToxicityInferenceService]


class ModelNotReadyError(RuntimeError):
    """Raised when runtime requests arrive before the model is available."""


class ModelReloadError(RuntimeError):
    """Raised when runtime reload cannot load a replacement model."""


@dataclass(slots=True, frozen=True)
class RuntimeReadiness:
    ready: bool
    detail: str | None
    model_path: str | None
    model_identity: ModelIdentity | None


def _default_service_loader(
    model_path: Path,
    *,
    artifacts: ModelArtifactPaths,
) -> ToxicityInferenceService:
    return ToxicityInferenceService.from_path(model_path, artifacts=artifacts)


class ModelRuntimeState:
    def __init__(
        self,
        *,
        default_model_path: Path = DEFAULT_MODEL_PATH,
        artifacts: ModelArtifactPaths = DEFAULT_ARTIFACT_PATHS,
        service_loader: RuntimeServiceLoader | None = None,
    ) -> None:
        self.default_model_path = default_model_path.resolve()
        self.artifacts = artifacts
        self._service_loader = service_loader or (
            lambda path: _default_service_loader(path, artifacts=artifacts)
        )
        self._lock = RLock()
        self._active_service: ToxicityInferenceService | None = None
        self._active_request_path: Path | None = None
        self._last_error: str | None = None

    def _format_load_error(self, exc: Exception, requested_path: Path) -> str:
        if isinstance(exc, FileNotFoundError):
            missing_path = Path(str(exc.args[0])) if exc.args else requested_path
            return build_missing_model_message(missing_path)
        message = str(exc).strip()
        return message or f"Failed to load model from {requested_path}."

    def initialize(self) -> None:
        try:
            self.reload()
        except ModelReloadError:
            return None

    def reload(self, model_path: Path | None = None) -> ToxicityInferenceService:
        requested_path = (
            model_path or self._active_request_path or self.default_model_path
        ).resolve()
        try:
            loaded_service = self._service_loader(requested_path)
        except Exception as exc:
            with self._lock:
                self._last_error = self._format_load_error(exc, requested_path)
            raise ModelReloadError(self._last_error) from exc
        with self._lock:
            self._active_service = loaded_service
            self._active_request_path = requested_path
            self._last_error = None
            return loaded_service

    def get_service(self) -> ToxicityInferenceService:
        with self._lock:
            service = self._active_service
            detail = self._last_error
        if service is None:
            raise ModelNotReadyError(detail or "Model runtime is not ready.")
        return service

    def readiness(self) -> RuntimeReadiness:
        with self._lock:
            service = self._active_service
            detail = self._last_error
        if service is None:
            return RuntimeReadiness(
                ready=False,
                detail=detail or "Model runtime is not ready.",
                model_path=None,
                model_identity=None,
            )
        identity = service.get_model_identity()
        return RuntimeReadiness(
            ready=True,
            detail=None,
            model_path=str(service.model_path) if service.model_path is not None else None,
            model_identity=identity,
        )
