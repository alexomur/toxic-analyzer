import re
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(tmp_root: Path, request: pytest.FixtureRequest) -> Path:
    prefix = re.sub(r"\W+", "-", request.node.name).strip("-") or "test"
    path = Path(tempfile.mkdtemp(prefix=f"{prefix}-", dir=tmp_root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture(scope="session")
def tmp_root() -> Path:
    root = Path(__file__).resolve().parents[1] / "test-temp-local"
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(exist_ok=True)
    return root


@pytest.fixture
def workspace_tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


def pytest_sessionfinish() -> None:
    root = Path(__file__).resolve().parents[1] / "test-temp-local"
    shutil.rmtree(root, ignore_errors=True)
