from pathlib import Path

import pytest

from toxic_analyzer import model_runtime
from toxic_analyzer.model_runtime import (
    ModelArtifactPaths,
    build_missing_model_message,
    load_baseline_model,
    resolve_model_path,
)


def test_resolve_model_path_returns_explicit_existing_path(tmp_path: Path) -> None:
    explicit_path = tmp_path / "baseline.pkl"
    explicit_path.write_bytes(b"stub")

    resolved = resolve_model_path(explicit_path)

    assert resolved == explicit_path.resolve()


def test_resolve_model_path_uses_fallback_for_missing_default(tmp_path: Path) -> None:
    default_path = tmp_path / "baseline-default.pkl"
    fallback_path = tmp_path / "baseline-fallback.pkl"
    fallback_path.write_bytes(b"stub")
    artifacts = ModelArtifactPaths(
        default_model_path=default_path,
        fallback_model_paths=(fallback_path,),
    )

    resolved = resolve_model_path(default_path, artifacts=artifacts)

    assert resolved == fallback_path.resolve()


def test_load_baseline_model_raises_when_no_model_exists(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.pkl"

    with pytest.raises(FileNotFoundError) as exc_info:
        load_baseline_model(missing_path)

    assert Path(str(exc_info.value.args[0])) == missing_path.resolve()


def test_load_baseline_model_returns_model_and_resolved_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = tmp_path / "baseline.pkl"
    model_path.write_bytes(b"stub")
    loaded_model = object()

    def fake_load(path: Path) -> object:
        assert path == model_path.resolve()
        return loaded_model

    monkeypatch.setattr(model_runtime.ToxicityBaselineModel, "load", staticmethod(fake_load))

    model, resolved = load_baseline_model(model_path)

    assert model is loaded_model
    assert resolved == model_path.resolve()


def test_build_missing_model_message_mentions_train_command(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.pkl"

    message = build_missing_model_message(missing_path)

    assert "train-baseline" in message
    assert str(missing_path) in message
