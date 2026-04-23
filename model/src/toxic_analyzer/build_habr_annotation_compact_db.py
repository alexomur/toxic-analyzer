"""Build a compact SQLite annotation database for Habr toxicity annotation."""


import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

from toxic_analyzer.paths import MODEL_ROOT

ROOT_DIR = MODEL_ROOT
DEFAULT_INPUT_JSONL_PATH = (
    ROOT_DIR / "data" / "processed" / "habr_comments_russian_annotation_pool.jsonl"
)
DEFAULT_OUTPUT_DB_PATH = (
    ROOT_DIR / "data" / "processed" / "habr_comments_annotation_compact.sqlite3"
)
BATCH_SIZE = 5000

SCHEMA_SQL = """
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA cache_size=-100000;

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    comment_id INTEGER NOT NULL UNIQUE,
    habr_score INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    toxic_label TEXT
        CHECK (toxic_label IS NULL OR toxic_label IN ('Да', 'Нет')),
    label_status TEXT NOT NULL
        CHECK (label_status IN ('pending', 'labeled', 'excluded'))
);

CREATE INDEX IF NOT EXISTS idx_comments_label_status
    ON comments(label_status);
"""

INSERT_SQL = """
INSERT INTO comments (
    id, comment_id, habr_score, raw_text, toxic_label, label_status
)
VALUES (:id, :comment_id, :habr_score, :raw_text, :toxic_label, :label_status)
"""


@dataclass(slots=True)
class CompactBuildConfig:
    input_jsonl: Path
    output_db: Path
    rebuild: bool


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-jsonl",
        type=Path,
        default=DEFAULT_INPUT_JSONL_PATH,
        help="Path to the cleaned JSONL produced by prepare_habr_comments.",
    )
    parser.add_argument(
        "--output-db",
        type=Path,
        default=DEFAULT_OUTPUT_DB_PATH,
        help="Path to the target compact SQLite database.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Delete the target database before rebuilding it.",
    )
    return parser.parse_args(argv)


def load_build_config(args: argparse.Namespace) -> CompactBuildConfig:
    return CompactBuildConfig(
        input_jsonl=args.input_jsonl.resolve(),
        output_db=args.output_db.resolve(),
        rebuild=args.rebuild,
    )


def create_connection(path: Path, rebuild: bool) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    if rebuild and path.exists():
        path.unlink()
    if path.exists():
        raise FileExistsError(
            f"Output DB already exists: {path}. Use --rebuild or choose another --output-db."
        )
    return sqlite3.connect(path)


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def iter_jsonl_rows(input_jsonl: Path) -> Iterator[dict[str, Any]]:
    with input_jsonl.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            payload = line.strip()
            if not payload:
                continue
            record = json.loads(payload)
            yield {
                "id": index,
                "comment_id": int(record["comment_id"]),
                "habr_score": int(record.get("habr_score") or 0),
                "raw_text": record.get("raw_text") or "",
                "toxic_label": None,
                "label_status": normalize_label_status_from_ready(
                    bool(record.get("is_annotation_ready"))
                ),
            }


def insert_compact_rows_from_jsonl(connection: sqlite3.Connection, input_jsonl: Path) -> int:
    batch: list[dict[str, Any]] = []
    inserted = 0

    for row in iter_jsonl_rows(input_jsonl):
        batch.append(row)
        if len(batch) >= BATCH_SIZE:
            connection.executemany(INSERT_SQL, batch)
            connection.commit()
            inserted += len(batch)
            batch.clear()

    if batch:
        connection.executemany(INSERT_SQL, batch)
        connection.commit()
        inserted += len(batch)

    return inserted


def count_rows(connection: sqlite3.Connection, label_status: str) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM comments WHERE label_status = ?",
            (label_status,),
        ).fetchone()[0]
    )


def normalize_label_status_from_ready(is_annotation_ready: bool) -> str:
    if is_annotation_ready:
        return "pending"
    return "excluded"


def run_build(config: CompactBuildConfig) -> dict[str, int]:
    if not config.input_jsonl.exists():
        raise FileNotFoundError(f"Input JSONL not found: {config.input_jsonl}")

    connection = create_connection(config.output_db, rebuild=config.rebuild)
    try:
        initialize_schema(connection)
        inserted_rows = insert_compact_rows_from_jsonl(connection, config.input_jsonl)
        connection.execute("VACUUM")
        return {
            "rows": inserted_rows,
            "pending_rows": count_rows(connection, "pending"),
            "labeled_rows": count_rows(connection, "labeled"),
            "excluded_rows": count_rows(connection, "excluded"),
        }
    finally:
        connection.close()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_build_config(args)
    stats = run_build(config)
    print(
        "[build-habr-annotation-compact-db] Done: "
        f"rows={stats['rows']} pending={stats['pending_rows']} "
        f"labeled={stats['labeled_rows']} excluded={stats['excluded_rows']}",
        flush=True,
    )
    print(f"[build-habr-annotation-compact-db] Output: {config.output_db}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
