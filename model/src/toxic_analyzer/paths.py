"""Helpers for locating the `model/` workspace from installed code."""


import os
from functools import lru_cache
from pathlib import Path

MODEL_ROOT_ENV_VAR = "TOXIC_ANALYZER_MODEL_ROOT"
_FALLBACK_ROOT = Path(__file__).resolve().parents[2]


def _looks_like_model_root(path: Path) -> bool:
    return (path / "pyproject.toml").is_file() and (path / "src").is_dir()


def _iter_search_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get(MODEL_ROOT_ENV_VAR)
    if env_root:
        candidates.append(Path(env_root).expanduser())

    module_path = Path(__file__).resolve()
    candidates.extend(module_path.parents)

    cwd = Path.cwd().resolve()
    candidates.extend((cwd, *cwd.parents))
    return candidates


@lru_cache(maxsize=1)
def resolve_model_root() -> Path:
    seen: set[Path] = set()
    for candidate in _iter_search_candidates():
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if _looks_like_model_root(resolved):
            return resolved
    return _FALLBACK_ROOT


MODEL_ROOT = resolve_model_root()
