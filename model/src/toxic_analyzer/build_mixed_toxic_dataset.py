"""Build a mixed SQLite dataset from dvach, OK, and Habr sources."""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DVACH_CSV_PATH = ROOT_DIR / "data" / "processed" / "labeled.csv"
DEFAULT_OK_DATASET_PATH = ROOT_DIR / "data" / "processed" / "dataset.txt"
DEFAULT_HABR_DB_PATH = ROOT_DIR / "data" / "processed" / "habr_comments_annotation_compact.sqlite3"
DEFAULT_OUTPUT_DB_PATH = ROOT_DIR / "data" / "processed" / "mixed_toxic_comments.sqlite3"
DEFAULT_REPORT_PATH = ROOT_DIR / "artifacts" / "mixed_toxic_comments_report.json"
RANDOM_SEED = 42
OK_LABELS_PATTERN = re.compile(r"^(?P<labels>(?:__label__[^\s,]+,?)+)\s+(?P<text>.*)$")

SCHEMA_SQL = """
PRAGMA journal_mode=OFF;
PRAGMA synchronous=OFF;
PRAGMA temp_store=MEMORY;
PRAGMA cache_size=-100000;

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL
        CHECK (source IN ('dvach', 'ok', 'habr')),
    source_row_id TEXT NOT NULL,
    source_comment_id INTEGER,
    raw_text TEXT NOT NULL,
    text_length INTEGER NOT NULL,
    is_toxic INTEGER
        CHECK (is_toxic IS NULL OR is_toxic IN (0, 1)),
    label_status TEXT NOT NULL
        CHECK (label_status IN ('labeled', 'pending')),
    source_labels TEXT,
    UNIQUE(source, source_row_id)
);

CREATE INDEX IF NOT EXISTS idx_mixed_comments_source
    ON comments(source);

CREATE INDEX IF NOT EXISTS idx_mixed_comments_label_status
    ON comments(label_status);

CREATE INDEX IF NOT EXISTS idx_mixed_comments_is_toxic
    ON comments(is_toxic);
"""


@dataclass(slots=True)
class MixedDatasetBuildConfig:
    dvach_csv: Path
    ok_dataset: Path
    habr_db: Path
    output_db: Path
    report_path: Path
    random_seed: int
    rebuild: bool


@dataclass(slots=True)
class SourceRow:
    source: str
    source_row_id: str
    source_comment_id: int | None
    raw_text: str
    is_toxic: bool | None
    label_status: str
    source_labels: str | None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dvach-csv", type=Path, default=DEFAULT_DVACH_CSV_PATH)
    parser.add_argument("--ok-dataset", type=Path, default=DEFAULT_OK_DATASET_PATH)
    parser.add_argument("--habr-db", type=Path, default=DEFAULT_HABR_DB_PATH)
    parser.add_argument("--output-db", type=Path, default=DEFAULT_OUTPUT_DB_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--random-seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--rebuild", action="store_true")
    return parser.parse_args(argv)


def load_build_config(args: argparse.Namespace) -> MixedDatasetBuildConfig:
    return MixedDatasetBuildConfig(
        dvach_csv=args.dvach_csv.resolve(),
        ok_dataset=args.ok_dataset.resolve(),
        habr_db=args.habr_db.resolve(),
        output_db=args.output_db.resolve(),
        report_path=args.report_path.resolve(),
        random_seed=int(args.random_seed),
        rebuild=bool(args.rebuild),
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


def normalize_text(text: str) -> str:
    return text.rstrip("\r\n")


def parse_ok_line(line: str) -> tuple[list[str], str]:
    match = OK_LABELS_PATTERN.match(line.rstrip("\n"))
    if match is None:
        raise ValueError(f"Unable to parse OK dataset line: {line[:120]!r}")
    labels = [part for part in match.group("labels").split(",") if part]
    return labels, normalize_text(match.group("text"))


def load_dvach_rows(path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, record in enumerate(reader, start=1):
            text = normalize_text(record["comment"])
            is_toxic = record["toxic"].strip() == "1.0"
            rows.append(
                SourceRow(
                    source="dvach",
                    source_row_id=str(index),
                    source_comment_id=None,
                    raw_text=text,
                    is_toxic=is_toxic,
                    label_status="labeled",
                    source_labels=record["toxic"].strip(),
                )
            )
    return rows


def load_ok_rows(path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            labels, text = parse_ok_line(line)
            is_toxic = any(label != "__label__NORMAL" for label in labels)
            rows.append(
                SourceRow(
                    source="ok",
                    source_row_id=str(index),
                    source_comment_id=None,
                    raw_text=text,
                    is_toxic=is_toxic,
                    label_status="labeled",
                    source_labels=",".join(labels),
                )
            )
    return rows


def select_labeled_rows(rows: list[SourceRow], rng: random.Random) -> list[SourceRow]:
    toxic_rows = [row for row in rows if row.is_toxic is True]
    non_toxic_rows = [row for row in rows if row.is_toxic is False]
    sample_size = len(non_toxic_rows) // 2
    selected_non_toxic = rng.sample(non_toxic_rows, sample_size)
    return toxic_rows + selected_non_toxic


def iter_habr_eligible_rows(connection: sqlite3.Connection) -> Iterator[SourceRow]:
    cursor = connection.execute(
        """
        SELECT id, comment_id, raw_text
        FROM comments
        WHERE label_status = 'pending'
        ORDER BY id
        """
    )
    for row_id, comment_id, raw_text in cursor:
        text = normalize_text(raw_text)
        if len(text) > 250 or "[code]" in text:
            continue
        yield SourceRow(
            source="habr",
            source_row_id=str(row_id),
            source_comment_id=int(comment_id),
            raw_text=text,
            is_toxic=None,
            label_status="pending",
            source_labels=None,
        )


def reservoir_sample(
    rows: Iterable[SourceRow],
    sample_size: int,
    rng: random.Random,
) -> list[SourceRow]:
    sample: list[SourceRow] = []
    for index, row in enumerate(rows):
        if index < sample_size:
            sample.append(row)
            continue
        replacement_index = rng.randint(0, index)
        if replacement_index < sample_size:
            sample[replacement_index] = row
    if len(sample) != sample_size:
        raise ValueError(
            "Unable to collect requested "
            f"sample_size={sample_size}. Got {len(sample)}."
        )
    return sample


def serialize_rows(rows: Iterable[SourceRow]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        payload.append(
            {
                "id": index,
                "source": row.source,
                "source_row_id": row.source_row_id,
                "source_comment_id": row.source_comment_id,
                "raw_text": row.raw_text,
                "text_length": len(row.raw_text),
                "is_toxic": None if row.is_toxic is None else int(row.is_toxic),
                "label_status": row.label_status,
                "source_labels": row.source_labels,
            }
        )
    return payload


def shuffle_rows(rows: list[SourceRow], rng: random.Random) -> list[SourceRow]:
    shuffled = list(rows)
    rng.shuffle(shuffled)
    return shuffled


def insert_rows(connection: sqlite3.Connection, rows: list[dict[str, object]]) -> None:
    connection.executemany(
        """
        INSERT INTO comments (
            id,
            source,
            source_row_id,
            source_comment_id,
            raw_text,
            text_length,
            is_toxic,
            label_status,
            source_labels
        )
        VALUES (
            :id,
            :source,
            :source_row_id,
            :source_comment_id,
            :raw_text,
            :text_length,
            :is_toxic,
            :label_status,
            :source_labels
        )
        """,
        rows,
    )
    connection.commit()


def count_by_source(rows: list[dict[str, object]]) -> dict[str, int]:
    stats = {"dvach": 0, "ok": 0, "habr": 0}
    for row in rows:
        stats[str(row["source"])] += 1
    return stats


def count_labeled_breakdown(rows: list[dict[str, object]], source: str) -> dict[str, int]:
    source_rows = [row for row in rows if row["source"] == source]
    toxic = sum(1 for row in source_rows if row["is_toxic"] == 1)
    non_toxic = sum(1 for row in source_rows if row["is_toxic"] == 0)
    pending = sum(1 for row in source_rows if row["is_toxic"] is None)
    return {"total": len(source_rows), "toxic": toxic, "non_toxic": non_toxic, "pending": pending}


def build_report(
    rows: list[dict[str, object]],
    config: MixedDatasetBuildConfig,
    dvach_non_toxic_sample: int,
    ok_non_toxic_sample: int,
) -> dict[str, object]:
    total_rows = len(rows)
    source_counts = count_by_source(rows)
    return {
        "random_seed": config.random_seed,
        "output_db": str(config.output_db),
        "sources": {
            "dvach": {
                **count_labeled_breakdown(rows, "dvach"),
                "share": round(source_counts["dvach"] / total_rows, 6),
                "sampled_non_toxic": dvach_non_toxic_sample,
            },
            "ok": {
                **count_labeled_breakdown(rows, "ok"),
                "share": round(source_counts["ok"] / total_rows, 6),
                "sampled_non_toxic": ok_non_toxic_sample,
            },
            "habr": {
                **count_labeled_breakdown(rows, "habr"),
                "share": round(source_counts["habr"] / total_rows, 6),
                "filter": {"max_text_length": 250, "exclude_substring": "[code]"},
            },
        },
        "totals": {
            "rows": total_rows,
            "labeled_rows": sum(1 for row in rows if row["label_status"] == "labeled"),
            "pending_rows": sum(1 for row in rows if row["label_status"] == "pending"),
        },
    }


def run_build(config: MixedDatasetBuildConfig) -> dict[str, object]:
    for path in (config.dvach_csv, config.ok_dataset, config.habr_db):
        if not path.exists():
            raise FileNotFoundError(path)

    rng = random.Random(config.random_seed)
    dvach_selected = select_labeled_rows(load_dvach_rows(config.dvach_csv), rng)
    ok_selected = select_labeled_rows(load_ok_rows(config.ok_dataset), rng)
    habr_sample_size = sum(1 for row in dvach_selected if row.is_toxic is False) + sum(
        1 for row in ok_selected if row.is_toxic is False
    )

    habr_connection = sqlite3.connect(config.habr_db)
    try:
        habr_selected = reservoir_sample(
            iter_habr_eligible_rows(habr_connection),
            habr_sample_size,
            rng,
        )
    finally:
        habr_connection.close()

    all_rows = serialize_rows(shuffle_rows(dvach_selected + ok_selected + habr_selected, rng))

    connection = create_connection(config.output_db, rebuild=config.rebuild)
    try:
        initialize_schema(connection)
        insert_rows(connection, all_rows)
        connection.execute("VACUUM")
    finally:
        connection.close()

    report = build_report(
        rows=all_rows,
        config=config,
        dvach_non_toxic_sample=sum(1 for row in dvach_selected if row.is_toxic is False),
        ok_non_toxic_sample=sum(1 for row in ok_selected if row.is_toxic is False),
    )
    config.report_path.parent.mkdir(parents=True, exist_ok=True)
    config.report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_build_config(args)
    report = run_build(config)
    print(
        "[build-mixed-toxic-dataset] Done: "
        f"rows={report['totals']['rows']} labeled={report['totals']['labeled_rows']} "
        f"pending={report['totals']['pending_rows']}",
        flush=True,
    )
    print(f"[build-mixed-toxic-dataset] Output DB: {config.output_db}", flush=True)
    print(f"[build-mixed-toxic-dataset] Report: {config.report_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
