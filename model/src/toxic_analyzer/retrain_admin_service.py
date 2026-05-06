"""Service layer for retrain jobs and model registry orchestration."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Callable

from toxic_analyzer.admin_store import PostgresAdminStore
from toxic_analyzer.admin_types import (
    AdminStore,
    BackgroundJobLauncher,
    ModelRegistryRecord,
    RetrainJobRecord,
    RetrainJobRequest,
    ThreadBackgroundJobLauncher,
    utcnow,
)
from toxic_analyzer.postgres_store import ConnectionFactory, PostgresSettings, redact_postgres_dsn
from toxic_analyzer.training_service import (
    DEFAULT_RETRAIN_ARTIFACTS_DIR,
    BaselineTrainingRequest,
    BaselineTrainingResult,
    compute_file_sha256,
    run_baseline_training,
    save_training_artifacts,
)


class RetrainAdminService:
    def __init__(
        self,
        *,
        store: AdminStore,
        background_launcher: BackgroundJobLauncher | None = None,
        training_runner: Callable[[BaselineTrainingRequest], BaselineTrainingResult] | None = None,
        artifact_dir: Path = DEFAULT_RETRAIN_ARTIFACTS_DIR,
        default_postgres_dsn: str | None = None,
        default_postgres_schema: str | None = None,
    ) -> None:
        self.store = store
        self.background_launcher = background_launcher or ThreadBackgroundJobLauncher()
        self.training_runner = training_runner or run_baseline_training
        self.artifact_dir = artifact_dir.resolve()
        self.default_postgres_dsn = default_postgres_dsn
        self.default_postgres_schema = default_postgres_schema

    @classmethod
    def from_postgres_settings(
        cls,
        settings: PostgresSettings,
        *,
        connection_factory: ConnectionFactory | None = None,
        background_launcher: BackgroundJobLauncher | None = None,
        training_runner: Callable[[BaselineTrainingRequest], BaselineTrainingResult] | None = None,
        artifact_dir: Path = DEFAULT_RETRAIN_ARTIFACTS_DIR,
    ) -> "RetrainAdminService":
        return cls(
            store=PostgresAdminStore(settings, connection_factory=connection_factory),
            background_launcher=background_launcher,
            training_runner=training_runner,
            artifact_dir=artifact_dir,
            default_postgres_dsn=settings.dsn,
            default_postgres_schema=settings.schema,
        )

    def _build_job_key(self) -> str:
        return f"retrain-{utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    def _build_model_key(self, *, job_key: str, model_version: str) -> str:
        normalized_version = model_version.replace(".", "_").strip() or "unknown"
        return f"baseline-{normalized_version}-{job_key}"

    def _build_artifact_paths(self, model_key: str) -> tuple[Path, Path]:
        base_name = model_key.replace("/", "_")
        model_path = self.artifact_dir / f"{base_name}.pkl"
        report_path = self.artifact_dir / f"{base_name}.report.json"
        return model_path, report_path

    def _build_dataset_snapshot(self, request: BaselineTrainingRequest) -> dict[str, Any]:
        return {
            "data_source": request.data_source,
            "dataset_path": str(request.dataset_path.resolve()),
            "postgres_dsn": redact_postgres_dsn(request.postgres_dsn)
            if request.postgres_dsn
            else None,
            "postgres_schema": request.postgres_schema,
            "dataset_cache_path": str(request.dataset_cache_path.resolve())
            if request.dataset_cache_path is not None
            else None,
            "refresh_dataset_cache": bool(request.refresh_dataset_cache),
            "random_seed": int(request.random_seed),
            "train_size": float(request.train_size),
            "validation_size": float(request.validation_size),
            "test_size": float(request.test_size),
        }

    def _resolve_training_request(self, request: RetrainJobRequest) -> BaselineTrainingRequest:
        training_request = request.training_request
        return BaselineTrainingRequest(
            data_source=training_request.data_source,
            dataset_path=training_request.dataset_path,
            postgres_dsn=training_request.postgres_dsn or self.default_postgres_dsn,
            postgres_schema=training_request.postgres_schema or self.default_postgres_schema,
            dataset_cache_path=training_request.dataset_cache_path,
            refresh_dataset_cache=training_request.refresh_dataset_cache,
            random_seed=training_request.random_seed,
            train_size=training_request.train_size,
            validation_size=training_request.validation_size,
            test_size=training_request.test_size,
            config=training_request.config,
            hard_case_dataset_path=training_request.hard_case_dataset_path,
            seed_dataset_path=training_request.seed_dataset_path,
        )

    def start_retrain(self, request: RetrainJobRequest) -> RetrainJobRecord:
        training_request = self._resolve_training_request(request)
        job_key = self._build_job_key()
        created_job = self.store.create_retrain_job(
            job_key=job_key,
            trigger_type=request.trigger_type,
            requested_by=request.requested_by,
            dataset_snapshot=self._build_dataset_snapshot(training_request),
            job_metadata={"requested_at": utcnow().isoformat()},
        )
        self.background_launcher.launch(lambda: self._run_retrain_job(job_key, training_request))
        return created_job

    def _run_retrain_job(self, job_key: str, training_request: BaselineTrainingRequest) -> None:
        try:
            self.store.mark_retrain_job_running(job_key)
            training_result = self.training_runner(training_request)
            model_version = str(training_result.model.metadata.get("model_version") or "unknown")
            model_key = self._build_model_key(job_key=job_key, model_version=model_version)
            training_result.model.metadata["model_key"] = model_key
            training_result.model.metadata["training_job_key"] = job_key
            model_output_path, report_output_path = self._build_artifact_paths(model_key)
            save_training_artifacts(
                training_result,
                model_output_path=model_output_path,
                report_output_path=report_output_path,
            )
            artifact_sha256 = compute_file_sha256(model_output_path)
            model_record = self.store.register_model(
                model_key=model_key,
                model_version=model_version,
                artifact_path=str(model_output_path),
                artifact_sha256=artifact_sha256,
                training_summary=training_result.report,
                metrics=dict(training_result.report.get("metrics") or {}),
            )
            self.store.mark_retrain_job_succeeded(
                job_key,
                output_model_id=model_record.id,
            )
        except Exception as exc:
            self.store.mark_retrain_job_failed(job_key, error_message=str(exc))

    def get_retrain_job(self, job_key: str) -> RetrainJobRecord | None:
        return self.store.get_retrain_job(job_key)

    def list_retrain_jobs(self, *, limit: int = 20) -> list[RetrainJobRecord]:
        return self.store.list_retrain_jobs(limit=limit)

    def get_model(self, model_key: str) -> ModelRegistryRecord | None:
        return self.store.get_model(model_key)
