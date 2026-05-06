"""Trusted server-side configuration for the internal model API boundary."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping

from toxic_analyzer.baseline_data import DEFAULT_MIXED_DATASET_PATH
from toxic_analyzer.model_runtime import DEFAULT_MODEL_PATH, ROOT_DIR
from toxic_analyzer.training_data import DEFAULT_TRAINING_DATA_CACHE_PATH


@dataclass(frozen=True, slots=True)
class InternalAuthOptions:
    enabled: bool = True
    header_name: str = "X-Internal-Api-Key"
    api_key: str | None = None


@dataclass(frozen=True, slots=True)
class CacheProfile:
    dataset_cache_path: Path | None
    refresh_dataset_cache: bool = False


@dataclass(frozen=True, slots=True)
class TrainingProfile:
    data_source: Literal["auto", "sqlite", "postgres", "cache"] = "auto"
    postgres_dsn: str | None = None
    postgres_schema: str | None = None


@dataclass(frozen=True, slots=True)
class AdminApiBoundary:
    enabled: bool = False
    artifacts_root: Path = ROOT_DIR / "artifacts"
    datasets_root: Path = ROOT_DIR / "data"
    caches_root: Path = ROOT_DIR / "data" / "cache"
    model_catalog: Mapping[str, Path] = field(
        default_factory=lambda: {"default": DEFAULT_MODEL_PATH}
    )
    dataset_catalog: Mapping[str, Path] = field(
        default_factory=lambda: {"mixed-default": DEFAULT_MIXED_DATASET_PATH}
    )
    cache_profiles: Mapping[str, CacheProfile] = field(
        default_factory=lambda: {
            "default": CacheProfile(DEFAULT_TRAINING_DATA_CACHE_PATH, refresh_dataset_cache=False),
            "refresh-default": CacheProfile(
                DEFAULT_TRAINING_DATA_CACHE_PATH, refresh_dataset_cache=True
            ),
            "disabled": CacheProfile(None, refresh_dataset_cache=False),
        }
    )
    training_profiles: Mapping[str, TrainingProfile] = field(
        default_factory=lambda: {
            "default": TrainingProfile(data_source="auto"),
            "sqlite-default": TrainingProfile(data_source="sqlite"),
            "postgres-default": TrainingProfile(data_source="postgres"),
            "cache-default": TrainingProfile(data_source="cache"),
        }
    )

    def resolve_model_path(self, model_id: str, *, registry_path: str | None = None) -> Path:
        if model_id in self.model_catalog:
            return _resolve_inside_root(self.artifacts_root, self.model_catalog[model_id])

        if registry_path is not None:
            return _resolve_inside_root(self.artifacts_root, Path(registry_path))

        raise KeyError(model_id)

    def resolve_dataset_path(self, dataset_id: str) -> Path:
        configured_path = self.dataset_catalog.get(dataset_id)
        if configured_path is None:
            raise KeyError(dataset_id)
        return _resolve_inside_root(self.datasets_root, configured_path)

    def resolve_cache_profile(self, cache_profile: str) -> CacheProfile:
        profile = self.cache_profiles.get(cache_profile)
        if profile is None:
            raise KeyError(cache_profile)

        if profile.dataset_cache_path is None:
            return profile

        return CacheProfile(
            dataset_cache_path=_resolve_inside_root(self.caches_root, profile.dataset_cache_path),
            refresh_dataset_cache=profile.refresh_dataset_cache,
        )

    def resolve_training_profile(self, training_profile: str) -> TrainingProfile:
        profile = self.training_profiles.get(training_profile)
        if profile is None:
            raise KeyError(training_profile)
        return profile


def load_internal_auth_options_from_env() -> InternalAuthOptions:
    enabled = _read_bool_env("MODEL_INTERNAL_AUTH_ENABLED", default=True)
    options = InternalAuthOptions(
        enabled=enabled,
        header_name=os.getenv("MODEL_INTERNAL_AUTH_HEADER_NAME", "X-Internal-Api-Key"),
        api_key=os.getenv("MODEL_INTERNAL_AUTH_KEY"),
    )
    if options.enabled and not options.api_key:
        raise RuntimeError("MODEL_INTERNAL_AUTH_KEY is required when internal auth is enabled.")
    return options


def load_admin_api_boundary_from_env(
    *,
    postgres_dsn: str | None,
    postgres_schema: str | None,
) -> AdminApiBoundary:
    enabled = _read_bool_env("MODEL_ADMIN_API_ENABLED", default=False)
    training_profiles = {
        "default": TrainingProfile(
            data_source="auto",
            postgres_dsn=postgres_dsn,
            postgres_schema=postgres_schema,
        ),
        "sqlite-default": TrainingProfile(data_source="sqlite"),
        "postgres-default": TrainingProfile(
            data_source="postgres",
            postgres_dsn=postgres_dsn,
            postgres_schema=postgres_schema,
        ),
        "cache-default": TrainingProfile(
            data_source="cache",
            postgres_dsn=postgres_dsn,
            postgres_schema=postgres_schema,
        ),
    }
    return AdminApiBoundary(enabled=enabled, training_profiles=training_profiles)


def _resolve_inside_root(root: Path, configured_path: Path) -> Path:
    resolved_root = root.resolve()
    candidate = (
        configured_path
        if configured_path.is_absolute()
        else resolved_root / configured_path
    )
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            f"Configured path escapes trusted root {resolved_root}: {configured_path}"
        ) from exc
    return resolved_candidate


def _read_bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}
