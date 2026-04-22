from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from toxic_analyzer.baseline_data import create_dataset_bundle_from_repository
from toxic_analyzer.postgres_store import PostgresSettings
from toxic_analyzer.training_data import (
    CachedTrainingDataRepository,
    PostgresTrainingDataRepository,
    TrainingDataRow,
    build_training_data_cache_metadata_path,
    resolve_training_data_repository,
    write_training_data_cache,
)


class StubRepository:
    def __init__(self, rows: list[TrainingDataRow], *, kind: str = "stub") -> None:
        self._rows = rows
        self._kind = kind

    def fetch_labeled_rows(self) -> list[TrainingDataRow]:
        return list(self._rows)

    def describe_source(self) -> dict[str, object]:
        return {"dataset_source": {"kind": self._kind}}


@dataclass
class FakeTrainingStore:
    rows: list[tuple[str, str, str, int]]
    executed_queries: list[str] = field(default_factory=list)


class FakeTrainingCursor:
    def __init__(self, store: FakeTrainingStore) -> None:
        self.store = store
        self._result: list[tuple[object, ...]] = []

    def execute(self, query: str) -> None:
        self.store.executed_queries.append(" ".join(query.split()))
        self._result = list(self.store.rows)

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._result)

    def close(self) -> None:
        return None


class FakeTrainingConnection:
    def __init__(self, store: FakeTrainingStore) -> None:
        self.store = store

    def cursor(self) -> FakeTrainingCursor:
        return FakeTrainingCursor(self.store)

    def close(self) -> None:
        return None


def make_training_connection_factory(store: FakeTrainingStore):
    def factory(dsn: str) -> FakeTrainingConnection:
        assert dsn.startswith("postgresql://")
        return FakeTrainingConnection(store)

    return factory


def build_sqlite_training_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE comments (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                text_length INTEGER NOT NULL,
                is_toxic INTEGER,
                label_status TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO comments (id, source, raw_text, text_length, is_toxic, label_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (1, "habr", "calm text", len("calm text"), 0, "labeled"),
                (2, "ok", "toxic text", len("toxic text"), 1, "labeled"),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def test_create_dataset_bundle_reassigns_sparse_source_strata() -> None:
    rows: list[TrainingDataRow] = []
    for source in ("habr", "ok"):
        for index in range(8):
            rows.append(
                TrainingDataRow(
                    row_id=f"{source}-safe-{index}",
                    source=source,
                    text=f"{source} safe text {index}",
                    label=0,
                )
            )
            rows.append(
                TrainingDataRow(
                    row_id=f"{source}-toxic-{index}",
                    source=source,
                    text=f"{source} toxic text {index}",
                    label=1,
                )
            )
    rows.append(
        TrainingDataRow(
            row_id="candidate-safe",
            source="feedback_curated",
            text="feedback curated safe",
            label=0,
        )
    )
    rows.append(
        TrainingDataRow(
            row_id="candidate-toxic",
            source="feedback_curated",
            text="feedback curated toxic",
            label=1,
        )
    )

    bundle = create_dataset_bundle_from_repository(StubRepository(rows), random_seed=5)

    assert len(bundle.train) + len(bundle.validation) + len(bundle.test) == len(rows)
    assert bundle.dataset_stats["stratification"]["rows_reassigned_to_label_only_strata"] == 2
    assert bundle.dataset_stats["stratification"]["sparse_primary_strata"] == {
        "feedback_curated:0": 1,
        "feedback_curated:1": 1,
    }


def test_postgres_training_repository_reads_rows_and_reports_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeTrainingStore(
        rows=[
            ("canonical:1", "habr", "normal text", 0),
            ("candidate:2", "feedback_curated", "bad text", 1),
        ]
    )
    monkeypatch.setattr(
        "toxic_analyzer.training_data.fetch_training_dataset_overview",
        lambda settings, connection_factory=None: {
            "rows": 2,
            "origin_counts": {"candidate": 1, "canonical": 1},
        },
    )
    repository = PostgresTrainingDataRepository(
        settings=PostgresSettings(
            dsn="postgresql://trainer:secret@example.com:5432/toxic",
            schema="toxic_analyzer_model",
        ),
        connection_factory=make_training_connection_factory(store),
    )

    rows = repository.fetch_labeled_rows()
    source_info = repository.describe_source()

    assert rows[0].row_id == "canonical:1"
    assert rows[1].source == "feedback_curated"
    assert source_info["dataset_source"]["kind"] == "postgres"
    assert source_info["dataset_source"]["dsn"] == "postgresql://trainer:***@example.com:5432/toxic"
    assert source_info["dataset_source"]["origin_counts"] == {"candidate": 1, "canonical": 1}


def test_resolve_training_data_repository_prefers_postgres_when_auto_and_env_present(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("TOXIC_ANALYZER_POSTGRES_DSN", "postgresql://trainer:secret@example.com/db")
    monkeypatch.setenv("TOXIC_ANALYZER_POSTGRES_SCHEMA", "toxic_analyzer_model")

    repository = resolve_training_data_repository(
        data_source="auto",
        dataset_path=tmp_path / "unused.sqlite3",
    )

    assert isinstance(repository, PostgresTrainingDataRepository)
    assert repository.settings.schema == "toxic_analyzer_model"


def test_resolve_training_data_repository_uses_cache_for_auto_offline_fallback(
    tmp_path: Path,
) -> None:
    cache_path = tmp_path / "training.jsonl.gz"
    write_training_data_cache(
        cache_path,
        rows=[
            TrainingDataRow(
                row_id="cached-1",
                source="habr",
                text="cached calm text",
                label=0,
            )
        ],
        source_info={"dataset_source": {"kind": "postgres", "dsn": "postgresql://trainer:***@db/app"}},
    )

    repository = resolve_training_data_repository(
        data_source="auto",
        dataset_path=tmp_path / "missing.sqlite3",
        dataset_cache_path=cache_path,
    )

    assert isinstance(repository, CachedTrainingDataRepository)
    assert repository.fetch_labeled_rows()[0].row_id == "cached-1"
    source_info = repository.describe_source()
    assert source_info["dataset_source"]["kind"] == "cache"
    assert source_info["dataset_source"]["source"]["kind"] == "postgres"


def test_resolve_training_data_repository_refreshes_cache_from_sqlite(
    tmp_path: Path,
) -> None:
    dataset_path = tmp_path / "mixed.sqlite3"
    cache_path = tmp_path / "training.jsonl.gz"
    build_sqlite_training_db(dataset_path)

    repository = resolve_training_data_repository(
        data_source="sqlite",
        dataset_path=dataset_path,
        dataset_cache_path=cache_path,
        refresh_dataset_cache=True,
    )

    rows = repository.fetch_labeled_rows()
    source_info = repository.describe_source()

    assert len(rows) == 2
    assert cache_path.exists()
    assert build_training_data_cache_metadata_path(cache_path).exists()
    assert source_info["dataset_source"]["kind"] == "cache"
    assert source_info["dataset_source"]["source"]["kind"] == "sqlite"
