"""Admin service layer for retrain jobs and model registry access."""


import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol

from toxic_analyzer.postgres_store import (
    ConnectionFactory,
    PostgresSettings,
    default_postgres_connection_factory,
    redact_postgres_dsn,
)
from toxic_analyzer.training_service import (
    DEFAULT_RETRAIN_ARTIFACTS_DIR,
    BaselineTrainingRequest,
    BaselineTrainingResult,
    compute_file_sha256,
    run_baseline_training,
    save_training_artifacts,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_json_object(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        loaded = json.loads(value)
        return dict(loaded) if isinstance(loaded, dict) else {}
    return dict(value)


def _coerce_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise TypeError(f"Unsupported datetime value: {value!r}")


def _close_quietly(resource: Any) -> None:
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


class PostgresAdminStore:
    def __init__(
        self,
        settings: PostgresSettings,
        *,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self.settings = settings
        self.connection_factory = connection_factory or default_postgres_connection_factory

    def _connect(self) -> Any:
        return self.connection_factory(self.settings.dsn)

    @staticmethod
    def _parse_model_row(row: tuple[Any, ...]) -> ModelRegistryRecord:
        return ModelRegistryRecord(
            id=int(row[0]),
            model_key=str(row[1]),
            model_family=str(row[2]),
            model_version=str(row[3]),
            artifact_path=str(row[4]),
            artifact_storage=str(row[5]),
            artifact_sha256=str(row[6]) if row[6] is not None else None,
            training_summary=_coerce_json_object(row[7]),
            metrics=_coerce_json_object(row[8]),
            status=str(row[9]),
            created_at=_coerce_datetime(row[10]) or _utcnow(),
            trained_at=_coerce_datetime(row[11]),
            promoted_at=_coerce_datetime(row[12]),
        )

    @staticmethod
    def _parse_retrain_job_row(row: tuple[Any, ...]) -> RetrainJobRecord:
        return RetrainJobRecord(
            id=int(row[0]),
            job_key=str(row[1]),
            job_type=str(row[2]),
            trigger_type=str(row[3]),
            status=str(row[4]),
            requested_by=str(row[5]) if row[5] is not None else None,
            output_model_id=int(row[6]) if row[6] is not None else None,
            dataset_snapshot=_coerce_json_object(row[7]),
            job_metadata=_coerce_json_object(row[8]),
            error_message=str(row[9]) if row[9] is not None else None,
            created_at=_coerce_datetime(row[10]) or _utcnow(),
            started_at=_coerce_datetime(row[11]),
            finished_at=_coerce_datetime(row[12]),
            output_model_key=str(row[13]) if row[13] is not None else None,
            output_model_version=str(row[14]) if row[14] is not None else None,
        )

    def create_retrain_job(
        self,
        *,
        job_key: str,
        trigger_type: str,
        requested_by: str | None,
        dataset_snapshot: dict[str, Any],
        job_metadata: dict[str, Any],
    ) -> RetrainJobRecord:
        query = f"""
            INSERT INTO {self.settings.schema}.retrain_jobs (
                job_key,
                job_type,
                trigger_type,
                requested_by,
                dataset_snapshot,
                job_metadata
            )
            VALUES (%s, 'retrain', %s, %s, CAST(%s AS JSONB), CAST(%s AS JSONB))
            RETURNING
                id,
                job_key,
                job_type,
                trigger_type,
                status,
                requested_by,
                output_model_id,
                dataset_snapshot,
                job_metadata,
                error_message,
                created_at,
                started_at,
                finished_at,
                NULL::TEXT AS output_model_key,
                NULL::TEXT AS output_model_version
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    query,
                    (
                        job_key,
                        trigger_type,
                        requested_by,
                        json.dumps(dataset_snapshot, ensure_ascii=False),
                        json.dumps(job_metadata, ensure_ascii=False),
                    ),
                )
                row = cursor.fetchone()
            finally:
                _close_quietly(cursor)
            connection.commit()
        finally:
            _close_quietly(connection)
        if row is None:
            raise RuntimeError("Failed to create retrain job row.")
        return self._parse_retrain_job_row(row)

    def _update_job_status(
        self,
        *,
        job_key: str,
        status: str,
        output_model_id: int | None = None,
        error_message: str | None = None,
        set_started_at: bool = False,
        set_finished_at: bool = False,
    ) -> RetrainJobRecord:
        query = f"""
            UPDATE {self.settings.schema}.retrain_jobs AS jobs
            SET
                status = %s,
                output_model_id = COALESCE(%s, jobs.output_model_id),
                error_message = %s,
                started_at = CASE
                    WHEN %s THEN COALESCE(jobs.started_at, NOW())
                    ELSE jobs.started_at
                END,
                finished_at = CASE WHEN %s THEN NOW() ELSE jobs.finished_at END
            WHERE jobs.job_key = %s
            RETURNING
                jobs.id,
                jobs.job_key,
                jobs.job_type,
                jobs.trigger_type,
                jobs.status,
                jobs.requested_by,
                jobs.output_model_id,
                jobs.dataset_snapshot,
                jobs.job_metadata,
                jobs.error_message,
                jobs.created_at,
                jobs.started_at,
                jobs.finished_at,
                (
                    SELECT registry.model_key
                    FROM {self.settings.schema}.model_registry AS registry
                    WHERE registry.id = jobs.output_model_id
                ) AS output_model_key,
                (
                    SELECT registry.model_version
                    FROM {self.settings.schema}.model_registry AS registry
                    WHERE registry.id = jobs.output_model_id
                ) AS output_model_version
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    query,
                    (
                        status,
                        output_model_id,
                        error_message,
                        set_started_at,
                        set_finished_at,
                        job_key,
                    ),
                )
                row = cursor.fetchone()
            finally:
                _close_quietly(cursor)
            connection.commit()
        finally:
            _close_quietly(connection)
        if row is None:
            raise KeyError(job_key)
        return self._parse_retrain_job_row(row)

    def mark_retrain_job_running(self, job_key: str) -> RetrainJobRecord:
        return self._update_job_status(
            job_key=job_key,
            status="running",
            set_started_at=True,
        )

    def mark_retrain_job_succeeded(
        self,
        job_key: str,
        *,
        output_model_id: int,
    ) -> RetrainJobRecord:
        return self._update_job_status(
            job_key=job_key,
            status="succeeded",
            output_model_id=output_model_id,
            error_message=None,
            set_finished_at=True,
        )

    def mark_retrain_job_failed(self, job_key: str, *, error_message: str) -> RetrainJobRecord:
        return self._update_job_status(
            job_key=job_key,
            status="failed",
            error_message=error_message,
            set_finished_at=True,
        )

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
        query = f"""
            INSERT INTO {self.settings.schema}.model_registry (
                model_key,
                model_family,
                model_version,
                artifact_path,
                artifact_storage,
                artifact_sha256,
                training_summary,
                metrics,
                status,
                trained_at
            )
            VALUES (
                %s,
                'baseline',
                %s,
                %s,
                'local_artifact',
                %s,
                CAST(%s AS JSONB),
                CAST(%s AS JSONB),
                'ready',
                NOW()
            )
            RETURNING
                id,
                model_key,
                model_family,
                model_version,
                artifact_path,
                artifact_storage,
                artifact_sha256,
                training_summary,
                metrics,
                status,
                created_at,
                trained_at,
                promoted_at
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    query,
                    (
                        model_key,
                        model_version,
                        artifact_path,
                        artifact_sha256,
                        json.dumps(training_summary, ensure_ascii=False),
                        json.dumps(metrics, ensure_ascii=False),
                    ),
                )
                row = cursor.fetchone()
            finally:
                _close_quietly(cursor)
            connection.commit()
        finally:
            _close_quietly(connection)
        if row is None:
            raise RuntimeError("Failed to register model row.")
        return self._parse_model_row(row)

    def get_model(self, model_key: str) -> ModelRegistryRecord | None:
        query = f"""
            SELECT
                id,
                model_key,
                model_family,
                model_version,
                artifact_path,
                artifact_storage,
                artifact_sha256,
                training_summary,
                metrics,
                status,
                created_at,
                trained_at,
                promoted_at
            FROM {self.settings.schema}.model_registry
            WHERE model_key = %s
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(query, (model_key,))
                row = cursor.fetchone()
            finally:
                _close_quietly(cursor)
        finally:
            _close_quietly(connection)
        return None if row is None else self._parse_model_row(row)

    def get_retrain_job(self, job_key: str) -> RetrainJobRecord | None:
        query = f"""
            SELECT
                jobs.id,
                jobs.job_key,
                jobs.job_type,
                jobs.trigger_type,
                jobs.status,
                jobs.requested_by,
                jobs.output_model_id,
                jobs.dataset_snapshot,
                jobs.job_metadata,
                jobs.error_message,
                jobs.created_at,
                jobs.started_at,
                jobs.finished_at,
                registry.model_key AS output_model_key,
                registry.model_version AS output_model_version
            FROM {self.settings.schema}.retrain_jobs AS jobs
            LEFT JOIN {self.settings.schema}.model_registry AS registry
                ON registry.id = jobs.output_model_id
            WHERE jobs.job_key = %s
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(query, (job_key,))
                row = cursor.fetchone()
            finally:
                _close_quietly(cursor)
        finally:
            _close_quietly(connection)
        return None if row is None else self._parse_retrain_job_row(row)

    def list_retrain_jobs(self, *, limit: int = 20) -> list[RetrainJobRecord]:
        query = f"""
            SELECT
                jobs.id,
                jobs.job_key,
                jobs.job_type,
                jobs.trigger_type,
                jobs.status,
                jobs.requested_by,
                jobs.output_model_id,
                jobs.dataset_snapshot,
                jobs.job_metadata,
                jobs.error_message,
                jobs.created_at,
                jobs.started_at,
                jobs.finished_at,
                registry.model_key AS output_model_key,
                registry.model_version AS output_model_version
            FROM {self.settings.schema}.retrain_jobs AS jobs
            LEFT JOIN {self.settings.schema}.model_registry AS registry
                ON registry.id = jobs.output_model_id
            ORDER BY jobs.created_at DESC
            LIMIT %s
        """
        connection = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(query, (limit,))
                rows = cursor.fetchall()
            finally:
                _close_quietly(cursor)
        finally:
            _close_quietly(connection)
        return [self._parse_retrain_job_row(row) for row in rows]


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
        return f"retrain-{_utcnow().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

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
            "postgres_dsn": (
                redact_postgres_dsn(request.postgres_dsn)
                if request.postgres_dsn
                else None
            ),
            "postgres_schema": request.postgres_schema,
            "dataset_cache_path": (
                str(request.dataset_cache_path.resolve())
                if request.dataset_cache_path is not None
                else None
            ),
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
            job_metadata={"requested_at": _utcnow().isoformat()},
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
