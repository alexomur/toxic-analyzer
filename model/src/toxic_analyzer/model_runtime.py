"""Shared runtime helpers for loading baseline model artifacts."""


from dataclasses import dataclass
from pathlib import Path
from typing import Final

from toxic_analyzer.baseline_model import ToxicityBaselineModel
from toxic_analyzer.paths import MODEL_ROOT

ROOT_DIR: Final[Path] = MODEL_ROOT
DEFAULT_MODEL_PATH: Final[Path] = ROOT_DIR / "artifacts" / "baseline_model_v3_3.pkl"
DEFAULT_FALLBACK_MODEL_PATHS: Final[tuple[Path, ...]] = (
    ROOT_DIR / "artifacts" / "baseline_model_v3_2.pkl",
    ROOT_DIR / "artifacts" / "baseline_model_v3_1.pkl",
    ROOT_DIR / "artifacts" / "baseline_model_v3.pkl",
    ROOT_DIR / "artifacts" / "baseline_model_v2.pkl",
    ROOT_DIR / "artifacts" / "baseline_model.pkl",
)


@dataclass(frozen=True, slots=True)
class ModelArtifactPaths:
    default_model_path: Path = DEFAULT_MODEL_PATH
    fallback_model_paths: tuple[Path, ...] = DEFAULT_FALLBACK_MODEL_PATHS


DEFAULT_ARTIFACT_PATHS: Final[ModelArtifactPaths] = ModelArtifactPaths()


def resolve_model_path(
    model_path: Path = DEFAULT_MODEL_PATH,
    *,
    artifacts: ModelArtifactPaths = DEFAULT_ARTIFACT_PATHS,
) -> Path:
    resolved_path = model_path.resolve()
    default_path = artifacts.default_model_path.resolve()
    if resolved_path.exists():
        return resolved_path
    if resolved_path != default_path:
        return resolved_path
    for fallback_path in artifacts.fallback_model_paths:
        resolved_fallback = fallback_path.resolve()
        if resolved_fallback.exists():
            return resolved_fallback
    return resolved_path


def load_baseline_model(
    model_path: Path = DEFAULT_MODEL_PATH,
    *,
    artifacts: ModelArtifactPaths = DEFAULT_ARTIFACT_PATHS,
) -> tuple[ToxicityBaselineModel, Path]:
    resolved_path = resolve_model_path(model_path, artifacts=artifacts)
    if not resolved_path.exists():
        raise FileNotFoundError(resolved_path)
    return ToxicityBaselineModel.load(resolved_path), resolved_path


def build_missing_model_message(resolved_path: Path) -> str:
    return (
        "Файл модели не найден. Сначала обучите baseline командой `train-baseline` "
        f"или укажите путь через --model-path: {resolved_path}"
    )
