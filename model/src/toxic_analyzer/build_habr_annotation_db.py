"""Build a SQLite preparation database for Habr toxicity annotation."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_PATH = (
    ROOT_DIR / "data" / "processed" / "habr_comments_russian_annotation_pool.jsonl"
)
DEFAULT_OUTPUT_PATH = ROOT_DIR / "data" / "processed" / "habr_comments_annotation_v2.sqlite3"

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA cache_size=-200000;

CREATE TABLE IF NOT EXISTS dataset_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    source_dataset TEXT NOT NULL,
    article_id INTEGER NOT NULL,
    article_title TEXT NOT NULL,
    article_url TEXT NOT NULL,
    article_time_published INTEGER NOT NULL,
    comment_id INTEGER NOT NULL UNIQUE,
    parent_comment_id INTEGER,
    level INTEGER NOT NULL,
    comment_time_published INTEGER NOT NULL,
    source_habr_score INTEGER NOT NULL,
    source_votes INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    clean_text TEXT NOT NULL,
    parent_clean_text TEXT,
    annotation_context TEXT NOT NULL,
    annotation_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (annotation_status IN ('pending', 'labeled', 'reviewed', 'excluded')),
    toxic_label TEXT
        CHECK (toxic_label IS NULL OR toxic_label IN ('Да', 'Нет')),
    label_confidence REAL
        CHECK (label_confidence IS NULL OR (label_confidence >= 0.0 AND label_confidence <= 1.0)),
    annotation_notes TEXT,
    exclusion_reason TEXT,
    is_russian INTEGER NOT NULL,
    is_mostly_code INTEGER NOT NULL,
    is_low_content INTEGER NOT NULL,
    is_annotation_ready INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_comments_annotation_status
    ON comments(annotation_status);
CREATE INDEX IF NOT EXISTS idx_comments_annotation_ready
    ON comments(is_annotation_ready, annotation_status);
CREATE INDEX IF NOT EXISTS idx_comments_article_id
    ON comments(article_id);
CREATE INDEX IF NOT EXISTS idx_comments_parent_comment_id
    ON comments(parent_comment_id);

CREATE VIEW IF NOT EXISTS annotation_queue AS
SELECT
    comment_id,
    article_id,
    article_title,
    level,
    annotation_status,
    toxic_label,
    label_confidence,
    clean_text,
    parent_clean_text,
    annotation_context,
    source_habr_score,
    source_votes
FROM comments
WHERE is_annotation_ready = 1
  AND annotation_status = 'pending';
"""

INSERT_SQL = """
INSERT INTO comments (
    source,
    source_dataset,
    article_id,
    article_title,
    article_url,
    article_time_published,
    comment_id,
    parent_comment_id,
    level,
    comment_time_published,
    source_habr_score,
    source_votes,
    raw_text,
    clean_text,
    parent_clean_text,
    annotation_context,
    annotation_status,
    toxic_label,
    label_confidence,
    annotation_notes,
    exclusion_reason,
    is_russian,
    is_mostly_code,
    is_low_content,
    is_annotation_ready,
    created_at,
    updated_at
) VALUES (
    :source,
    :source_dataset,
    :article_id,
    :article_title,
    :article_url,
    :article_time_published,
    :comment_id,
    :parent_comment_id,
    :level,
    :comment_time_published,
    :source_habr_score,
    :source_votes,
    :raw_text,
    :clean_text,
    NULL,
    :annotation_context,
    :annotation_status,
    NULL,
    NULL,
    NULL,
    NULL,
    :is_russian,
    :is_mostly_code,
    :is_low_content,
    :is_annotation_ready,
    :created_at,
    :updated_at
);
"""

BACKFILL_PARENT_SQL = """
UPDATE comments
SET
    parent_clean_text = (
        SELECT parent.clean_text
        FROM comments AS parent
        WHERE parent.comment_id = comments.parent_comment_id
        LIMIT 1
    ),
    annotation_context = CASE
        WHEN parent_comment_id IS NULL OR parent_comment_id = 0 THEN
            'Статья: ' || article_title || char(10) || char(10) ||
            'Комментарий:' || char(10) || clean_text
        ELSE
            'Статья: ' || article_title || char(10) || char(10) ||
            'Родительский комментарий:' || char(10) ||
            COALESCE((
                SELECT parent.clean_text
                FROM comments AS parent
                WHERE parent.comment_id = comments.parent_comment_id
                LIMIT 1
            ), '[контекст недоступен]') || char(10) || char(10) ||
            'Комментарий:' || char(10) || clean_text
    END,
    updated_at = :updated_at;
"""


@dataclass(slots=True)
class BuildConfig:
    input_jsonl: Path
    output_db: Path
    source_dataset: str
    batch_size: int
    rebuild: bool


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the cleaned JSONL produced by prepare_habr_comments.",
    )
    parser.add_argument(
        "--output-db",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the target SQLite database.",
    )
    parser.add_argument(
        "--source-dataset",
        default="IlyaGusev/habr",
        help="Source dataset label to persist in the database.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="SQLite executemany batch size.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the target database before rebuilding it.",
    )
    return parser.parse_args(argv)


def load_build_config(args: argparse.Namespace) -> BuildConfig:
    return BuildConfig(
        input_jsonl=args.input_jsonl.resolve(),
        output_db=args.output_db.resolve(),
        source_dataset=args.source_dataset,
        batch_size=args.batch_size,
        rebuild=args.rebuild,
    )


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def create_connection(path: Path, rebuild: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rebuild and path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=OFF;")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def upsert_meta(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO dataset_meta(key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, value),
    )


def comment_to_row(record: dict[str, Any], source_dataset: str, timestamp: str) -> dict[str, Any]:
    parent_comment_id = int(record.get("parent_id") or 0)
    parent_comment_value = parent_comment_id if parent_comment_id != 0 else None

    return {
        "source": "habr",
        "source_dataset": source_dataset,
        "article_id": int(record["article_id"]),
        "article_title": record.get("article_title") or "",
        "article_url": record.get("article_url") or "",
        "article_time_published": int(record.get("article_time_published") or 0),
        "comment_id": int(record["comment_id"]),
        "parent_comment_id": parent_comment_value,
        "level": int(record.get("level") or 0),
        "comment_time_published": int(record.get("time_published") or 0),
        "source_habr_score": int(record.get("habr_score") or 0),
        "source_votes": int(record.get("votes") or 0),
        "raw_text": record.get("raw_text") or "",
        "clean_text": record.get("clean_text") or "",
        "annotation_context": build_annotation_context(
            article_title=record.get("article_title") or "",
            clean_text=record.get("clean_text") or "",
            parent_clean_text=None,
        ),
        "annotation_status": infer_annotation_status(record),
        "is_russian": int(bool(record.get("is_russian"))),
        "is_mostly_code": int(bool(record.get("is_mostly_code"))),
        "is_low_content": int(bool(record.get("is_low_content"))),
        "is_annotation_ready": int(bool(record.get("is_annotation_ready"))),
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def infer_annotation_status(record: dict[str, Any]) -> str:
    if bool(record.get("is_annotation_ready")):
        return "pending"
    return "excluded"


def build_annotation_context(
    *,
    article_title: str,
    clean_text: str,
    parent_clean_text: str | None,
) -> str:
    parts = [f"Статья: {article_title}".strip()]
    if parent_clean_text:
        parts.append(f"Родительский комментарий:\n{parent_clean_text}")
    parts.append(f"Комментарий:\n{clean_text}")
    return "\n\n".join(parts)


def insert_jsonl(
    connection: sqlite3.Connection,
    *,
    input_jsonl: Path,
    source_dataset: str,
    batch_size: int,
) -> int:
    inserted = 0
    batch: list[dict[str, Any]] = []

    with input_jsonl.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            payload = line.strip()
            if not payload:
                continue
            record = json.loads(payload)
            timestamp = utc_now_iso()
            batch.append(comment_to_row(record, source_dataset, timestamp))

            if len(batch) >= batch_size:
                connection.executemany(INSERT_SQL, batch)
                connection.commit()
                inserted += len(batch)
                print(
                    f"[build-habr-annotation-db] inserted={inserted} source_lines={line_number}",
                    flush=True,
                )
                batch.clear()

        if batch:
            connection.executemany(INSERT_SQL, batch)
            connection.commit()
            inserted += len(batch)
            print(
                f"[build-habr-annotation-db] inserted={inserted} source_lines={line_number}",
                flush=True,
            )

    return inserted


def backfill_parent_context(connection: sqlite3.Connection) -> None:
    timestamp = utc_now_iso()
    connection.execute(BACKFILL_PARENT_SQL, {"updated_at": timestamp})
    connection.commit()


def count_rows(connection: sqlite3.Connection, where: str = "1=1") -> int:
    query = f"SELECT COUNT(*) FROM comments WHERE {where}"
    return int(connection.execute(query).fetchone()[0])


def finalize_meta(
    connection: sqlite3.Connection,
    *,
    config: BuildConfig,
    imported_rows: int,
) -> None:
    pending_rows = count_rows(connection, "annotation_status = 'pending'")
    excluded_rows = count_rows(connection, "annotation_status = 'excluded'")
    rows_with_parent_context = count_rows(
        connection,
        "parent_comment_id IS NOT NULL AND parent_clean_text IS NOT NULL",
    )

    upsert_meta(connection, "source_dataset", config.source_dataset)
    upsert_meta(connection, "input_jsonl", str(config.input_jsonl))
    upsert_meta(connection, "output_db", str(config.output_db))
    upsert_meta(connection, "imported_rows", str(imported_rows))
    upsert_meta(connection, "pending_rows", str(pending_rows))
    upsert_meta(connection, "excluded_rows", str(excluded_rows))
    upsert_meta(connection, "rows_with_parent_context", str(rows_with_parent_context))
    upsert_meta(connection, "built_at", utc_now_iso())
    connection.commit()


def run_build(config: BuildConfig) -> dict[str, int]:
    if not config.input_jsonl.exists():
        raise FileNotFoundError(f"Input JSONL not found: {config.input_jsonl}")

    connection = create_connection(config.output_db, rebuild=config.rebuild)
    try:
        initialize_schema(connection)
        imported_rows = insert_jsonl(
            connection,
            input_jsonl=config.input_jsonl,
            source_dataset=config.source_dataset,
            batch_size=config.batch_size,
        )
        print("[build-habr-annotation-db] backfilling parent context", flush=True)
        backfill_parent_context(connection)
        finalize_meta(connection, config=config, imported_rows=imported_rows)

        return {
            "imported_rows": imported_rows,
            "pending_rows": count_rows(connection, "annotation_status = 'pending'"),
            "excluded_rows": count_rows(connection, "annotation_status = 'excluded'"),
            "rows_with_parent_context": count_rows(
                connection,
                "parent_comment_id IS NOT NULL AND parent_clean_text IS NOT NULL",
            ),
        }
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_build_config(args)
    stats = run_build(config)
    print(
        "[build-habr-annotation-db] Done: "
        f"imported={stats['imported_rows']} pending={stats['pending_rows']} "
        f"excluded={stats['excluded_rows']} parent_context={stats['rows_with_parent_context']}",
        flush=True,
    )
    print(f"[build-habr-annotation-db] Output: {config.output_db}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
