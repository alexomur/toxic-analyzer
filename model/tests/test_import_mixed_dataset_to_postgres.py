from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from toxic_analyzer.import_mixed_dataset_to_postgres import (
    load_sqlite_rows_for_postgres_import,
    run_import,
)
from toxic_analyzer.postgres_store import PostgresSettings


def build_legacy_sqlite_dataset(path: Path) -> None:
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
                (1, "habr", "normal text", len("normal text"), 0, "labeled"),
                (2, "ok", "toxic text", len("toxic text"), 1, "labeled"),
                (3, "habr", "pending text", len("pending text"), None, "pending"),
            ],
        )
        connection.commit()
    finally:
        connection.close()


@dataclass
class FakeImportStore:
    canonical_rows: dict[tuple[str, str, str], dict[str, object]] = field(default_factory=dict)
    executed_batch_sizes: list[int] = field(default_factory=list)
    applied_sql: list[str] = field(default_factory=list)


class FakeImportCursor:
    def __init__(self, store: FakeImportStore) -> None:
        self.store = store
        self._result: list[tuple[object, ...]] = []

    def execute(self, query: str, params: tuple[object, ...] | None = None) -> None:
        normalized = " ".join(query.split()).lower()
        self.store.applied_sql.append(normalized)
        origin_system = None if params is None else str(params[0])
        rows = [
            row
            for row in self.store.canonical_rows.values()
            if origin_system is None or row["origin_system"] == origin_system
        ]
        if normalized.startswith("select count(*) from"):
            self._result = [(len(rows),)]
            return
        if "select source, count(*)" in normalized:
            counts: dict[str, int] = {}
            for row in rows:
                counts[str(row["source"])] = counts.get(str(row["source"]), 0) + 1
            self._result = [(source, count) for source, count in sorted(counts.items())]
            return
        if "select label_status, count(*)" in normalized:
            counts: dict[str, int] = {}
            for row in rows:
                counts[str(row["label_status"])] = counts.get(str(row["label_status"]), 0) + 1
            self._result = [(status, count) for status, count in sorted(counts.items())]
            return
        if "select label, count(*)" in normalized:
            counts: dict[int, int] = {}
            for row in rows:
                label = int(row["label"])
                counts[label] = counts.get(label, 0) + 1
            self._result = [(label, count) for label, count in sorted(counts.items())]
            return
        if "select source, label_status, count(*)" in normalized:
            counts: dict[tuple[str, str], int] = {}
            for row in rows:
                key = (str(row["source"]), str(row["label_status"]))
                counts[key] = counts.get(key, 0) + 1
            self._result = [
                (source, status, count) for (source, status), count in sorted(counts.items())
            ]
            return
        self._result = []

    def executemany(self, query: str, params_list: list[tuple[object, ...]]) -> None:
        self.store.executed_batch_sizes.append(len(params_list))
        for params in params_list:
            (
                source,
                source_record_id,
                source_comment_id,
                raw_text,
                normalized_text,
                text_length,
                label,
                label_status,
                source_labels,
                origin_system,
            ) = params
            key = (str(origin_system), str(source), str(source_record_id))
            self.store.canonical_rows[key] = {
                "source": str(source),
                "source_record_id": str(source_record_id),
                "source_comment_id": source_comment_id,
                "raw_text": str(raw_text),
                "normalized_text": str(normalized_text),
                "text_length": int(text_length),
                "label": int(label),
                "label_status": str(label_status),
                "source_labels": source_labels,
                "origin_system": str(origin_system),
            }

    def fetchone(self) -> tuple[object, ...]:
        return self._result[0]

    def fetchall(self) -> list[tuple[object, ...]]:
        return list(self._result)

    def close(self) -> None:
        return None


class FakeImportConnection:
    def __init__(self, store: FakeImportStore) -> None:
        self.store = store

    def cursor(self) -> FakeImportCursor:
        return FakeImportCursor(self.store)

    def commit(self) -> None:
        return None

    def close(self) -> None:
        return None


def make_import_connection_factory(store: FakeImportStore):
    def factory(dsn: str) -> FakeImportConnection:
        assert dsn.startswith("postgresql://")
        return FakeImportConnection(store)

    return factory


def test_load_sqlite_rows_for_postgres_import_supports_legacy_schema(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "mixed.sqlite3"
    build_legacy_sqlite_dataset(sqlite_path)

    rows, summary = load_sqlite_rows_for_postgres_import(sqlite_path, origin_system="mixed_sqlite")

    assert len(rows) == 2
    assert rows[0].source_record_id == "1"
    assert rows[1].normalized_text == "toxic text"
    assert summary["rows_in_comments_table"] == 3
    assert summary["rows_selected_for_import"] == 2
    assert summary["raw_status_counts"] == {"labeled": 2, "pending": 1}


def test_run_import_batches_upserts_and_validates_counts(tmp_path: Path) -> None:
    sqlite_path = tmp_path / "mixed.sqlite3"
    build_legacy_sqlite_dataset(sqlite_path)
    store = FakeImportStore()
    settings = PostgresSettings(
        dsn="postgresql://trainer:secret@example.com:5432/toxic",
        schema="toxic_analyzer_model",
    )

    summary = run_import(
        sqlite_path=sqlite_path,
        settings=settings,
        batch_size=1,
        origin_system="mixed_sqlite",
        apply_schema=True,
        connection_factory=make_import_connection_factory(store),
    )

    assert summary["postgres"]["rows"] == 2
    assert summary["postgres"]["source_counts"] == {"habr": 1, "ok": 1}
    assert summary["postgres_target"]["dsn"] == "postgresql://trainer:***@example.com:5432/toxic"
    assert store.executed_batch_sizes == [1, 1]
    assert any(
        "create schema if not exists toxic_analyzer_model" in sql for sql in store.applied_sql
    )
