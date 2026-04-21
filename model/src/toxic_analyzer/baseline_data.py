"""Utilities for loading and splitting the mixed toxicity dataset."""

from __future__ import annotations

import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from sklearn.model_selection import train_test_split

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MIXED_DATASET_PATH = ROOT_DIR / "data" / "processed" / "mixed_toxic_comments.sqlite3"
ALLOWED_SOURCES = {"dvach", "ok", "habr"}


@dataclass(slots=True)
class CommentRecord:
    row_id: int
    source: str
    text: str
    label: int


@dataclass(slots=True)
class DatasetSplit:
    name: str
    row_ids: list[int]
    texts: list[str]
    labels: list[int]
    sources: list[str]

    def __len__(self) -> int:
        return len(self.texts)

    def to_summary(self) -> dict[str, Any]:
        label_counts = Counter(self.labels)
        source_counts = Counter(self.sources)
        stratum_counts = Counter(
            f"{source}:{label}" for source, label in zip(self.sources, self.labels, strict=True)
        )
        return {
            "rows": len(self),
            "label_counts": {"0": label_counts.get(0, 0), "1": label_counts.get(1, 0)},
            "source_counts": dict(sorted(source_counts.items())),
            "stratum_counts": dict(sorted(stratum_counts.items())),
        }


@dataclass(slots=True)
class DatasetBundle:
    train: DatasetSplit
    validation: DatasetSplit
    test: DatasetSplit
    dataset_stats: dict[str, Any]


def normalize_text_key(text: str) -> str:
    return " ".join(text.split())


def _validate_split_sizes(train_size: float, validation_size: float, test_size: float) -> None:
    total = train_size + validation_size + test_size
    if not 0 < train_size < 1:
        raise ValueError(f"train_size must be between 0 and 1. Got {train_size!r}.")
    if not 0 < validation_size < 1:
        raise ValueError(f"validation_size must be between 0 and 1. Got {validation_size!r}.")
    if not 0 < test_size < 1:
        raise ValueError(f"test_size must be between 0 and 1. Got {test_size!r}.")
    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            "train_size + validation_size + test_size must equal 1.0. "
            f"Got {train_size} + {validation_size} + {test_size} = {total}."
        )


def load_labeled_comments(
    dataset_path: Path,
    *,
    drop_conflicting_texts: bool = True,
    deduplicate: bool = True,
) -> tuple[list[CommentRecord], dict[str, Any]]:
    if not dataset_path.exists():
        raise FileNotFoundError(dataset_path)

    connection = sqlite3.connect(dataset_path)
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

    raw_records: list[CommentRecord] = []
    text_labels: dict[str, set[int]] = defaultdict(set)
    for row_id, source, text, label in rows:
        if source not in ALLOWED_SOURCES:
            raise ValueError(f"Unsupported source={source!r} in dataset.")
        normalized_text = normalize_text_key(str(text))
        label_int = int(label)
        raw_records.append(
            CommentRecord(
                row_id=int(row_id),
                source=str(source),
                text=str(text),
                label=label_int,
            )
        )
        text_labels[normalized_text].add(label_int)

    conflicting_texts = {
        normalized_text for normalized_text, labels in text_labels.items() if len(labels) > 1
    }

    cleaned_records: list[CommentRecord] = []
    seen_keys: set[tuple[str, int]] = set()
    dropped_conflicting_rows = 0
    dropped_duplicate_rows = 0

    for record in raw_records:
        normalized_text = normalize_text_key(record.text)
        if drop_conflicting_texts and normalized_text in conflicting_texts:
            dropped_conflicting_rows += 1
            continue
        dedup_key = (normalized_text, record.label)
        if deduplicate and dedup_key in seen_keys:
            dropped_duplicate_rows += 1
            continue
        if deduplicate:
            seen_keys.add(dedup_key)
        cleaned_records.append(record)

    label_counts = Counter(record.label for record in cleaned_records)
    source_counts = Counter(record.source for record in cleaned_records)
    stratum_counts = Counter(
        f"{record.source}:{record.label}" for record in cleaned_records
    )
    dataset_stats = {
        "dataset_path": str(dataset_path),
        "loaded_rows": len(raw_records),
        "kept_rows": len(cleaned_records),
        "dropped_conflicting_rows": dropped_conflicting_rows,
        "dropped_duplicate_rows": dropped_duplicate_rows,
        "ambiguous_text_count": len(conflicting_texts),
        "label_counts": {"0": label_counts.get(0, 0), "1": label_counts.get(1, 0)},
        "source_counts": dict(sorted(source_counts.items())),
        "stratum_counts": dict(sorted(stratum_counts.items())),
    }
    return cleaned_records, dataset_stats


def _build_split(
    name: str,
    records: Sequence[CommentRecord],
    indices: Iterable[int],
) -> DatasetSplit:
    selected = [records[index] for index in indices]
    return DatasetSplit(
        name=name,
        row_ids=[record.row_id for record in selected],
        texts=[record.text for record in selected],
        labels=[record.label for record in selected],
        sources=[record.source for record in selected],
    )


def create_dataset_bundle(
    dataset_path: Path = DEFAULT_MIXED_DATASET_PATH,
    *,
    train_size: float = 0.7,
    validation_size: float = 0.15,
    test_size: float = 0.15,
    random_seed: int = 42,
    drop_conflicting_texts: bool = True,
    deduplicate: bool = True,
) -> DatasetBundle:
    _validate_split_sizes(train_size, validation_size, test_size)
    records, dataset_stats = load_labeled_comments(
        dataset_path=dataset_path,
        drop_conflicting_texts=drop_conflicting_texts,
        deduplicate=deduplicate,
    )
    if len(records) < 3:
        raise ValueError("Need at least three labeled rows to create train/validation/test splits.")

    indices = list(range(len(records)))
    strata = [f"{record.source}:{record.label}" for record in records]

    train_indices, temp_indices = train_test_split(
        indices,
        train_size=train_size,
        random_state=random_seed,
        stratify=strata,
    )
    temp_strata = [strata[index] for index in temp_indices]
    validation_fraction = validation_size / (validation_size + test_size)
    validation_indices, test_indices = train_test_split(
        temp_indices,
        train_size=validation_fraction,
        random_state=random_seed,
        stratify=temp_strata,
    )

    bundle = DatasetBundle(
        train=_build_split("train", records, train_indices),
        validation=_build_split("validation", records, validation_indices),
        test=_build_split("test", records, test_indices),
        dataset_stats=dataset_stats,
    )
    bundle.dataset_stats["splits"] = {
        "train": bundle.train.to_summary(),
        "validation": bundle.validation.to_summary(),
        "test": bundle.test.to_summary(),
    }
    return bundle
