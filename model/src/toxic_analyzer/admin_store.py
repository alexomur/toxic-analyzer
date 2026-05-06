"""Store implementations for model retrain jobs and registry access."""

from __future__ import annotations

import json
from typing import Any

from toxic_analyzer.admin_types import (
    ModelRegistryRecord,
    RetrainJobRecord,
    close_quietly,
    coerce_datetime,
    coerce_json_object,
    utcnow,
)
from toxic_analyzer.postgres_store import (
    ConnectionFactory,
    PostgresSettings,
    default_postgres_connection_factory,
)


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
            training_summary=coerce_json_object(row[7]),
            metrics=coerce_json_object(row[8]),
            status=str(row[9]),
            created_at=coerce_datetime(row[10]) or utcnow(),
            trained_at=coerce_datetime(row[11]),
            promoted_at=coerce_datetime(row[12]),
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
            dataset_snapshot=coerce_json_object(row[7]),
            job_metadata=coerce_json_object(row[8]),
            error_message=str(row[9]) if row[9] is not None else None,
            created_at=coerce_datetime(row[10]) or utcnow(),
            started_at=coerce_datetime(row[11]),
            finished_at=coerce_datetime(row[12]),
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
                close_quietly(cursor)
            connection.commit()
        finally:
            close_quietly(connection)
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
                close_quietly(cursor)
            connection.commit()
        finally:
            close_quietly(connection)
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
                close_quietly(cursor)
            connection.commit()
        finally:
            close_quietly(connection)
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
                close_quietly(cursor)
        finally:
            close_quietly(connection)
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
                close_quietly(cursor)
        finally:
            close_quietly(connection)
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
                close_quietly(cursor)
        finally:
            close_quietly(connection)
        return [self._parse_retrain_job_row(row) for row in rows]
