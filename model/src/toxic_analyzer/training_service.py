"""Reusable training service for baseline model CLI and admin flows."""


import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from toxic_analyzer.baseline_data import (
    DEFAULT_MIXED_DATASET_PATH,
    create_dataset_bundle_from_repository,
)
from toxic_analyzer.baseline_model import (
    BaselineTrainingConfig,
    ToxicityBaselineModel,
    train_baseline_model,
)
from toxic_analyzer.hard_case_dataset import HardCaseDataset, load_hard_case_dataset
from toxic_analyzer.paths import MODEL_ROOT
from toxic_analyzer.training_data import (
    DEFAULT_TRAINING_DATA_CACHE_PATH,
    resolve_training_data_repository,
)

ROOT_DIR = MODEL_ROOT
DEFAULT_HARD_CASE_DATASET_PATH = ROOT_DIR / "configs" / "baseline_hard_cases_v3.jsonl"
DEFAULT_SEED_DATASET_PATH = ROOT_DIR / "configs" / "baseline_seed_examples_v3.jsonl"
DEFAULT_MODEL_OUTPUT_PATH = ROOT_DIR / "artifacts" / "baseline_model_v3_3.pkl"
DEFAULT_REPORT_OUTPUT_PATH = ROOT_DIR / "artifacts" / "baseline_training_report_v3_3.json"
DEFAULT_RETRAIN_ARTIFACTS_DIR = ROOT_DIR / "artifacts" / "retrain"


@dataclass(slots=True)
class BaselineTrainingRequest:
    data_source: str = "auto"
    dataset_path: Path = DEFAULT_MIXED_DATASET_PATH
    postgres_dsn: str | None = None
    postgres_schema: str | None = None
    dataset_cache_path: Path | None = DEFAULT_TRAINING_DATA_CACHE_PATH
    refresh_dataset_cache: bool = False
    random_seed: int = 42
    train_size: float = 0.7
    validation_size: float = 0.15
    test_size: float = 0.15
    config: BaselineTrainingConfig = field(default_factory=BaselineTrainingConfig)
    hard_case_dataset_path: Path = DEFAULT_HARD_CASE_DATASET_PATH
    seed_dataset_path: Path = DEFAULT_SEED_DATASET_PATH


@dataclass(slots=True)
class BaselineTrainingResult:
    model: ToxicityBaselineModel
    report: dict[str, Any]


def _load_optional_hard_case_dataset(path: Path) -> HardCaseDataset | None:
    resolved_path = path.resolve()
    if not resolved_path.exists():
        return None
    return load_hard_case_dataset(resolved_path)


def run_baseline_training(request: BaselineTrainingRequest) -> BaselineTrainingResult:
    repository = resolve_training_data_repository(
        data_source=str(request.data_source),
        dataset_path=request.dataset_path.resolve(),
        postgres_dsn=request.postgres_dsn,
        postgres_schema=request.postgres_schema,
        dataset_cache_path=(
            request.dataset_cache_path.resolve()
            if request.dataset_cache_path is not None
            else None
        ),
        refresh_dataset_cache=bool(request.refresh_dataset_cache),
    )
    dataset_bundle = create_dataset_bundle_from_repository(
        repository,
        train_size=float(request.train_size),
        validation_size=float(request.validation_size),
        test_size=float(request.test_size),
        random_seed=int(request.random_seed),
    )
    hard_case_dataset = _load_optional_hard_case_dataset(request.hard_case_dataset_path)
    seed_dataset = _load_optional_hard_case_dataset(request.seed_dataset_path)
    model, report = train_baseline_model(
        dataset_bundle,
        config=request.config,
        hard_case_dataset=hard_case_dataset,
        seed_dataset=seed_dataset,
    )
    return BaselineTrainingResult(model=model, report=report)


def save_training_artifacts(
    result: BaselineTrainingResult,
    *,
    model_output_path: Path,
    report_output_path: Path,
) -> None:
    resolved_model_output = model_output_path.resolve()
    resolved_report_output = report_output_path.resolve()
    result.model.save(resolved_model_output)
    resolved_report_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_output.write_text(
        json.dumps(result.report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
