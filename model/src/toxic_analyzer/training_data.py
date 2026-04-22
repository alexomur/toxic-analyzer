"""Repository layer for baseline training data."""

from __future__ import annotations

import copy
import gzip
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from toxic_analyzer.postgres_store import (
    TRAINING_DATASET_VIEW_NAME,
    ConnectionFactory,
    PostgresSettings,
    default_postgres_connection_factory,
    fetch_training_dataset_overview,
    resolve_postgres_settings,
)

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TRAINING_DATA_CACHE_PATH = ROOT_DIR / "data" / "cache" / "baseline_training_dataset.jsonl.gz"


@dataclass(slots=True)
class TrainingDataRow:
    row_id: str
    source: str
    text: str
    label: int


class TrainingDataRepository(Protocol):
    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        ...

    def describe_source(self) -> dict[str, Any]:
        ...


@dataclass(slots=True)
class InMemoryTrainingDataRepository:
    rows: list[TrainingDataRow]
    source_info: dict[str, Any]

    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        return list(self.rows)

    def describe_source(self) -> dict[str, Any]:
        return copy.deepcopy(self.source_info)


@dataclass(slots=True)
class SQLiteTrainingDataRepository:
    dataset_path: Path

    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        if not self.dataset_path.exists():
            raise FileNotFoundError(self.dataset_path)

        connection = sqlite3.connect(self.dataset_path)
        try:
            rows = connection.execute(
                """
                SELECT id, source, raw_text, is_toxic
                FROM comments
                WHERE label_status = 'labeled'
                  AND is_toxic IS NOT NULL
                ORDER BY id
                """
            ).fetchall()
        finally:
            connection.close()

        return [
            TrainingDataRow(
                row_id=str(row_id),
                source=str(source),
                text=str(text),
                label=int(label),
            )
            for row_id, source, text, label in rows
        ]

    def describe_source(self) -> dict[str, Any]:
        return {
            "dataset_source": {
                "kind": "sqlite",
                "path": str(self.dataset_path),
            }
        }


@dataclass(slots=True)
class PostgresTrainingDataRepository:
    settings: PostgresSettings
    connection_factory: ConnectionFactory | None = None

    def _connection_factory(self) -> ConnectionFactory:
        return self.connection_factory or default_postgres_connection_factory

    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        query = f"""
            SELECT record_key, source, raw_text, label
            FROM {self.settings.schema}.{TRAINING_DATASET_VIEW_NAME}
            ORDER BY source, record_key
        """
        connection = self._connection_factory()(self.settings.dsn)
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(query)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()

        return [
            TrainingDataRow(
                row_id=str(row_id),
                source=str(source),
                text=str(text),
                label=int(label),
            )
            for row_id, source, text, label in rows
        ]

    def describe_source(self) -> dict[str, Any]:
        overview = fetch_training_dataset_overview(
            self.settings,
            connection_factory=self._connection_factory(),
        )
        return {
            "dataset_source": {
                "kind": "postgres",
                "dsn": self.settings.redacted_dsn(),
                "schema": self.settings.schema,
                "view": TRAINING_DATASET_VIEW_NAME,
                "origin_counts": overview["origin_counts"],
            }
        }


def build_training_data_cache_metadata_path(cache_path: Path) -> Path:
    return Path(f"{cache_path}.metadata.json")


def _build_cached_source_info(
    *,
    cache_path: Path,
    created_at: str,
    rows: int,
    source_info: dict[str, Any],
) -> dict[str, Any]:
    original_source = copy.deepcopy(source_info.get("dataset_source", source_info))
    return {
        "dataset_source": {
            "kind": "cache",
            "path": str(cache_path),
            "created_at": created_at,
            "rows": int(rows),
            "source": original_source,
        }
    }


def write_training_data_cache(
    cache_path: Path,
    *,
    rows: list[TrainingDataRow],
    source_info: dict[str, Any],
) -> dict[str, Any]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = build_training_data_cache_metadata_path(cache_path)
    temp_cache_path = cache_path.with_name(f"{cache_path.name}.tmp")
    temp_metadata_path = metadata_path.with_name(f"{metadata_path.name}.tmp")
    created_at = datetime.now(timezone.utc).isoformat()

    with gzip.open(temp_cache_path, "wt", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    {
                        "row_id": row.row_id,
                        "source": row.source,
                        "text": row.text,
                        "label": row.label,
                    },
                    ensure_ascii=False,
                )
            )
            handle.write("\n")

    cached_source_info = _build_cached_source_info(
        cache_path=cache_path,
        created_at=created_at,
        rows=len(rows),
        source_info=source_info,
    )
    temp_metadata_path.write_text(
        json.dumps(
            {
                "cache_version": 1,
                "created_at": created_at,
                "rows": len(rows),
                "source_info": cached_source_info,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_cache_path.replace(cache_path)
    temp_metadata_path.replace(metadata_path)
    return cached_source_info


def load_training_data_cache(cache_path: Path) -> tuple[list[TrainingDataRow], dict[str, Any]]:
    if not cache_path.exists():
        raise FileNotFoundError(cache_path)

    rows: list[TrainingDataRow] = []
    with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            rows.append(
                TrainingDataRow(
                    row_id=str(payload["row_id"]),
                    source=str(payload["source"]),
                    text=str(payload["text"]),
                    label=int(payload["label"]),
                )
            )

    metadata_path = build_training_data_cache_metadata_path(cache_path)
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        source_info = metadata.get("source_info") or {}
    else:
        source_info = {
            "dataset_source": {
                "kind": "cache",
                "path": str(cache_path),
                "rows": len(rows),
            }
        }
    return rows, source_info


@dataclass(slots=True)
class CachedTrainingDataRepository:
    cache_path: Path
    _rows: list[TrainingDataRow] | None = None
    _source_info: dict[str, Any] | None = None

    def _ensure_loaded(self) -> None:
        if self._rows is None or self._source_info is None:
            self._rows, self._source_info = load_training_data_cache(self.cache_path)

    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        self._ensure_loaded()
        return list(self._rows or [])

    def describe_source(self) -> dict[str, Any]:
        self._ensure_loaded()
        return copy.deepcopy(self._source_info or {})


def materialize_training_data_cache(
    repository: TrainingDataRepository,
    *,
    cache_path: Path,
) -> TrainingDataRepository:
    rows = repository.fetch_labeled_rows()
    source_info = repository.describe_source()
    cached_source_info = write_training_data_cache(
        cache_path,
        rows=rows,
        source_info=source_info,
    )
    return InMemoryTrainingDataRepository(rows=rows, source_info=cached_source_info)


def resolve_training_data_repository(
    *,
    data_source: str,
    dataset_path: Path,
    postgres_dsn: str | None = None,
    postgres_schema: str | None = None,
    dataset_cache_path: Path | None = DEFAULT_TRAINING_DATA_CACHE_PATH,
    refresh_dataset_cache: bool = False,
    connection_factory: ConnectionFactory | None = None,
) -> TrainingDataRepository:
    normalized_source = data_source.lower().strip()
    if normalized_source not in {"auto", "sqlite", "postgres", "cache"}:
        raise ValueError(
            "Unsupported data_source. Expected one of 'auto', 'sqlite', 'postgres', or 'cache', "
            f"got {data_source!r}."
        )

    resolved_cache_path = dataset_cache_path.resolve() if dataset_cache_path is not None else None

    if normalized_source == "cache":
        if resolved_cache_path is None:
            raise ValueError("dataset_cache_path is required when data_source='cache'.")
        if refresh_dataset_cache:
            raise ValueError(
                "Cannot refresh dataset cache when data_source='cache'. "
                "Use 'sqlite', 'postgres', or 'auto' to rebuild the cache from the source data."
            )
        return CachedTrainingDataRepository(cache_path=resolved_cache_path)

    if normalized_source == "sqlite":
        repository: TrainingDataRepository = SQLiteTrainingDataRepository(dataset_path=dataset_path)
        if refresh_dataset_cache and resolved_cache_path is not None:
            return materialize_training_data_cache(repository, cache_path=resolved_cache_path)
        return repository

    settings = resolve_postgres_settings(
        dsn=postgres_dsn,
        schema=postgres_schema,
        require=normalized_source == "postgres",
    )
    if settings is not None:
        repository = PostgresTrainingDataRepository(
            settings=settings,
            connection_factory=connection_factory,
        )
        if refresh_dataset_cache and resolved_cache_path is not None:
            return materialize_training_data_cache(repository, cache_path=resolved_cache_path)
        return repository

    if refresh_dataset_cache:
        repository = SQLiteTrainingDataRepository(dataset_path=dataset_path)
        if resolved_cache_path is not None:
            return materialize_training_data_cache(repository, cache_path=resolved_cache_path)
        return repository

    if resolved_cache_path is not None and resolved_cache_path.exists() and not dataset_path.exists():
        return CachedTrainingDataRepository(cache_path=resolved_cache_path)

    return SQLiteTrainingDataRepository(dataset_path=dataset_path)
