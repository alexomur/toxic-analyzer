"""Import the legacy mixed SQLite dataset into PostgreSQL canonical training texts."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

from toxic_analyzer.baseline_data import DEFAULT_MIXED_DATASET_PATH, normalize_text_key
from toxic_analyzer.postgres_store import (
    CanonicalTrainingImportRow,
    ConnectionFactory,
    PostgresSettings,
    apply_postgres_migrations,
    fetch_canonical_import_summary,
    resolve_postgres_settings,
    upsert_canonical_training_rows,
)

DEFAULT_IMPORT_ORIGIN_SYSTEM = "mixed_sqlite"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-path", type=Path, default=DEFAULT_MIXED_DATASET_PATH)
    parser.add_argument("--postgres-dsn")
    parser.add_argument("--postgres-schema")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--origin-system", default=DEFAULT_IMPORT_ORIGIN_SYSTEM)
    parser.add_argument("--apply-schema", action="store_true")
    return parser.parse_args(argv)


def load_sqlite_rows_for_postgres_import(
    sqlite_path: Path,
    *,
    origin_system: str,
) -> tuple[list[CanonicalTrainingImportRow], dict[str, Any]]:
    if not sqlite_path.exists():
        raise FileNotFoundError(sqlite_path)

    connection = sqlite3.connect(sqlite_path)
    try:
        columns = {str(name) for _, name, *_ in connection.execute("PRAGMA table_info(comments)")}
        required_columns = {"id", "source", "raw_text", "is_toxic", "label_status"}
        missing_columns = sorted(required_columns - columns)
        if missing_columns:
            raise ValueError(
                "SQLite dataset is missing required columns: "
                f"{', '.join(missing_columns)}."
            )

        source_record_expr = (
            "CAST(source_row_id AS TEXT)" if "source_row_id" in columns else "CAST(id AS TEXT)"
        )
        source_comment_expr = (
            "CAST(source_comment_id AS TEXT)" if "source_comment_id" in columns else "NULL"
        )
        source_labels_expr = "source_labels" if "source_labels" in columns else "NULL"

        cursor = connection.execute(
            f"""
            SELECT
                id,
                source,
                raw_text,
                is_toxic,
                label_status,
                {source_record_expr} AS source_record_id,
                {source_comment_expr} AS source_comment_id,
                {source_labels_expr} AS source_labels
            FROM comments
            ORDER BY id
            """
        )
        fetched_rows = cursor.fetchall()
    finally:
        connection.close()

    status_counts = Counter()
    source_counts = Counter()
    source_status_counts = Counter()
    imported_rows: list[CanonicalTrainingImportRow] = []

    for (
        row_id,
        source,
        raw_text,
        label,
        label_status,
        source_record_id,
        source_comment_id,
        source_labels,
    ) in fetched_rows:
        status_key = str(label_status)
        source_key = str(source)
        status_counts[status_key] += 1
        source_counts[source_key] += 1
        source_status_counts[f"{source_key}:{status_key}"] += 1

        if label_status != "labeled" or label is None:
            continue

        text = str(raw_text)
        imported_rows.append(
            CanonicalTrainingImportRow(
                source=source_key,
                source_record_id=str(source_record_id or row_id),
                source_comment_id=None if source_comment_id is None else str(source_comment_id),
                raw_text=text,
                normalized_text=normalize_text_key(text),
                text_length=len(text),
                label=int(label),
                source_labels=None if source_labels is None else str(source_labels),
                origin_system=origin_system,
            )
        )

    imported_source_counts = Counter(row.source for row in imported_rows)
    imported_label_counts = Counter(str(row.label) for row in imported_rows)
    imported_source_status_counts = Counter(
        f"{row.source}:{row.label_status}" for row in imported_rows
    )
    sqlite_summary = {
        "sqlite_path": str(sqlite_path),
        "rows_in_comments_table": len(fetched_rows),
        "rows_selected_for_import": len(imported_rows),
        "rows_skipped": len(fetched_rows) - len(imported_rows),
        "source_counts": dict(sorted(imported_source_counts.items())),
        "label_status_counts": {"labeled": len(imported_rows)},
        "label_counts": dict(sorted(imported_label_counts.items())),
        "source_status_counts": dict(sorted(imported_source_status_counts.items())),
        "raw_source_counts": dict(sorted(source_counts.items())),
        "raw_status_counts": dict(sorted(status_counts.items())),
        "raw_source_status_counts": dict(sorted(source_status_counts.items())),
    }
    return imported_rows, sqlite_summary


def validate_import_summary(
    *,
    sqlite_summary: dict[str, Any],
    postgres_summary: dict[str, Any],
) -> None:
    expected = {
        "rows_selected_for_import": int(sqlite_summary["rows_selected_for_import"]),
        "source_counts": dict(sqlite_summary["source_counts"]),
        "label_status_counts": dict(sqlite_summary["label_status_counts"]),
        "label_counts": dict(sqlite_summary["label_counts"]),
        "source_status_counts": dict(sqlite_summary["source_status_counts"]),
    }
    actual = {
        "rows_selected_for_import": int(postgres_summary["rows"]),
        "source_counts": dict(postgres_summary["source_counts"]),
        "label_status_counts": dict(postgres_summary["label_status_counts"]),
        "label_counts": dict(postgres_summary["label_counts"]),
        "source_status_counts": dict(postgres_summary["source_status_counts"]),
    }
    for key, expected_value in expected.items():
        if expected_value != actual[key]:
            raise ValueError(
                "PostgreSQL import validation failed for "
                f"{key!r}. expected={expected_value!r} actual={actual[key]!r}."
            )


def run_import(
    *,
    sqlite_path: Path,
    settings: PostgresSettings,
    batch_size: int,
    origin_system: str,
    apply_schema: bool = False,
    connection_factory: ConnectionFactory | None = None,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise ValueError(f"batch_size must be positive. Got {batch_size!r}.")

    if apply_schema:
        apply_postgres_migrations(settings, connection_factory=connection_factory)

    import_rows, sqlite_summary = load_sqlite_rows_for_postgres_import(
        sqlite_path,
        origin_system=origin_system,
    )
    upserted_rows = upsert_canonical_training_rows(
        settings,
        import_rows,
        batch_size=batch_size,
        connection_factory=connection_factory,
    )
    postgres_summary = fetch_canonical_import_summary(
        settings,
        origin_system=origin_system,
        connection_factory=connection_factory,
    )
    validate_import_summary(sqlite_summary=sqlite_summary, postgres_summary=postgres_summary)
    return {
        "postgres_target": {
            "dsn": settings.redacted_dsn(),
            "schema": settings.schema,
            "origin_system": origin_system,
        },
        "sqlite": sqlite_summary,
        "postgres": postgres_summary,
        "upserted_rows": upserted_rows,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = resolve_postgres_settings(
        dsn=args.postgres_dsn,
        schema=args.postgres_schema,
        require=True,
    )
    summary = run_import(
        sqlite_path=args.sqlite_path.resolve(),
        settings=settings,
        batch_size=int(args.batch_size),
        origin_system=str(args.origin_system),
        apply_schema=bool(args.apply_schema),
    )
    print(
        "[import-mixed-dataset-to-postgres] Done: "
        f"rows={summary['postgres']['rows']} schema={settings.schema}",
        flush=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
