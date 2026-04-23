"""Utilities for loading and splitting the mixed toxicity dataset."""


import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from sklearn.model_selection import train_test_split

from toxic_analyzer.paths import MODEL_ROOT
from toxic_analyzer.training_data import (
    SQLiteTrainingDataRepository,
    TrainingDataRepository,
)

ROOT_DIR = MODEL_ROOT
DEFAULT_MIXED_DATASET_PATH = ROOT_DIR / "data" / "processed" / "mixed_toxic_comments.sqlite3"


@dataclass(slots=True)
class CommentRecord:
    row_id: str
    source: str
    text: str
    label: int


@dataclass(slots=True)
class DatasetSplit:
    name: str
    row_ids: list[str]
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
    repository = SQLiteTrainingDataRepository(dataset_path=dataset_path)
    return load_labeled_comments_from_repository(
        repository,
        drop_conflicting_texts=drop_conflicting_texts,
        deduplicate=deduplicate,
    )


def load_labeled_comments_from_repository(
    repository: TrainingDataRepository,
    *,
    drop_conflicting_texts: bool = True,
    deduplicate: bool = True,
) -> tuple[list[CommentRecord], dict[str, Any]]:
    rows = repository.fetch_labeled_rows()
    dataset_stats = repository.describe_source()

    raw_records: list[CommentRecord] = []
    text_labels: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        source = str(row.source).strip()
        if not source:
            raise ValueError("Training data source names must be non-empty strings.")
        text = str(row.text)
        normalized_text = normalize_text_key(text)
        label_int = int(row.label)
        if label_int not in {0, 1}:
            raise ValueError(f"Expected binary labels 0/1, got {row.label!r}.")
        raw_records.append(
            CommentRecord(
                row_id=str(row.row_id),
                source=source,
                text=text,
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
        **dataset_stats,
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


def _split_indices_two_stage(
    indices: Sequence[int],
    strata: Sequence[str],
    *,
    train_size: float,
    validation_size: float,
    test_size: float,
    random_seed: int,
) -> tuple[list[int], list[int], list[int]]:
    index_to_stratum = {index: stratum for index, stratum in zip(indices, strata, strict=True)}
    train_indices, temp_indices = train_test_split(
        list(indices),
        train_size=train_size,
        random_state=random_seed,
        stratify=list(strata),
    )
    temp_strata = [index_to_stratum[index] for index in temp_indices]
    validation_fraction = validation_size / (validation_size + test_size)
    validation_indices, test_indices = train_test_split(
        temp_indices,
        train_size=validation_fraction,
        random_state=random_seed,
        stratify=temp_strata,
    )
    return train_indices, validation_indices, test_indices


def _split_indices_without_stratification(
    indices: Sequence[int],
    *,
    train_size: float,
    validation_size: float,
    test_size: float,
    random_seed: int,
) -> tuple[list[int], list[int], list[int]]:
    shuffled = list(indices)
    random.Random(random_seed).shuffle(shuffled)
    train_end = int(round(len(shuffled) * train_size))
    validation_end = train_end + int(round(len(shuffled) * validation_size))
    train_indices = shuffled[:train_end]
    validation_indices = shuffled[train_end:validation_end]
    test_indices = shuffled[validation_end:]
    return train_indices, validation_indices, test_indices


def _split_indices_with_sparse_strata(
    records: Sequence[CommentRecord],
    *,
    train_size: float,
    validation_size: float,
    test_size: float,
    random_seed: int,
) -> tuple[list[int], list[int], list[int], dict[str, Any]]:
    primary_strata = [f"{record.source}:{record.label}" for record in records]
    primary_counts = Counter(primary_strata)
    held_out_fraction = validation_size + test_size
    min_rows_per_primary_stratum = max(2, math.ceil(2.0 / held_out_fraction))
    sparse_primary_strata = {
        stratum: count
        for stratum, count in primary_counts.items()
        if count < min_rows_per_primary_stratum
    }

    if not sparse_primary_strata:
        train_indices, validation_indices, test_indices = _split_indices_two_stage(
            list(range(len(records))),
            primary_strata,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            random_seed=random_seed,
        )
        return train_indices, validation_indices, test_indices, {
            "min_rows_per_primary_stratum": min_rows_per_primary_stratum,
            "sparse_primary_strata": {},
            "rows_reassigned_to_label_only_strata": 0,
            "sparse_rows_assigned_without_source_stratification": 0,
        }

    dense_indices = [
        index
        for index, primary_stratum in enumerate(primary_strata)
        if primary_stratum not in sparse_primary_strata
    ]
    dense_strata = [primary_strata[index] for index in dense_indices]
    sparse_indices_by_label: dict[int, list[int]] = defaultdict(list)
    for index, primary_stratum in enumerate(primary_strata):
        if primary_stratum in sparse_primary_strata:
            sparse_indices_by_label[records[index].label].append(index)

    train_indices: list[int]
    validation_indices: list[int]
    test_indices: list[int]
    if dense_indices:
        train_indices, validation_indices, test_indices = _split_indices_two_stage(
            dense_indices,
            dense_strata,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            random_seed=random_seed,
        )
    else:
        train_indices, validation_indices, test_indices = [], [], []

    sparse_rows = 0
    for label, sparse_indices in sorted(sparse_indices_by_label.items()):
        sparse_rows += len(sparse_indices)
        sparse_train, sparse_validation, sparse_test = _split_indices_without_stratification(
            sparse_indices,
            train_size=train_size,
            validation_size=validation_size,
            test_size=test_size,
            random_seed=random_seed + 1000 + label,
        )
        train_indices.extend(sparse_train)
        validation_indices.extend(sparse_validation)
        test_indices.extend(sparse_test)

    return sorted(train_indices), sorted(validation_indices), sorted(test_indices), {
        "min_rows_per_primary_stratum": min_rows_per_primary_stratum,
        "sparse_primary_strata": dict(sorted(sparse_primary_strata.items())),
        "rows_reassigned_to_label_only_strata": sparse_rows,
        "sparse_rows_assigned_without_source_stratification": sparse_rows,
    }


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
    repository = SQLiteTrainingDataRepository(dataset_path=dataset_path)
    return create_dataset_bundle_from_repository(
        repository,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        random_seed=random_seed,
        drop_conflicting_texts=drop_conflicting_texts,
        deduplicate=deduplicate,
    )


def create_dataset_bundle_from_repository(
    repository: TrainingDataRepository,
    *,
    train_size: float = 0.7,
    validation_size: float = 0.15,
    test_size: float = 0.15,
    random_seed: int = 42,
    drop_conflicting_texts: bool = True,
    deduplicate: bool = True,
) -> DatasetBundle:
    _validate_split_sizes(train_size, validation_size, test_size)
    records, dataset_stats = load_labeled_comments_from_repository(
        repository=repository,
        drop_conflicting_texts=drop_conflicting_texts,
        deduplicate=deduplicate,
    )
    if len(records) < 3:
        raise ValueError("Need at least three labeled rows to create train/validation/test splits.")

    train_indices, validation_indices, test_indices, stratification_stats = (
        _split_indices_with_sparse_strata(
        records,
        train_size=train_size,
        validation_size=validation_size,
        test_size=test_size,
        random_seed=random_seed,
        )
    )

    bundle = DatasetBundle(
        train=_build_split("train", records, train_indices),
        validation=_build_split("validation", records, validation_indices),
        test=_build_split("test", records, test_indices),
        dataset_stats=dataset_stats,
    )
    bundle.dataset_stats["stratification"] = stratification_stats
    bundle.dataset_stats["splits"] = {
        "train": bundle.train.to_summary(),
        "validation": bundle.validation.to_summary(),
        "test": bundle.test.to_summary(),
    }
    return bundle
