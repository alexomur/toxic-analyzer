from pathlib import Path

from toxic_analyzer import paths


def _make_model_root(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "src").mkdir(exist_ok=True)
    (path / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")
    return path.resolve()


def test_resolve_model_root_prefers_env_var(
    tmp_path: Path,
    monkeypatch,
) -> None:
    expected_root = _make_model_root(tmp_path / "env-root")
    monkeypatch.setenv(paths.MODEL_ROOT_ENV_VAR, str(expected_root))
    paths.resolve_model_root.cache_clear()

    assert paths.resolve_model_root() == expected_root
    paths.resolve_model_root.cache_clear()


def test_resolve_model_root_uses_first_matching_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    invalid_root = tmp_path / "not-a-model-root"
    expected_root = _make_model_root(tmp_path / "candidate-root")
    monkeypatch.setattr(
        paths,
        "_iter_search_candidates",
        lambda: [invalid_root, expected_root],
    )
    paths.resolve_model_root.cache_clear()

    assert paths.resolve_model_root() == expected_root
    paths.resolve_model_root.cache_clear()
