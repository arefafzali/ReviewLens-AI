"""Pytest bootstrap fixtures for backend tests."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(autouse=True)
def set_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide mandatory environment values for tests."""

    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")


@pytest.fixture
def client() -> TestClient:
    """Return a test client with clean, test-scoped settings cache."""

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    test_client = TestClient(app)
    get_settings.cache_clear()
    return test_client


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the root path for backend test fixtures."""

    return Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def read_fixture_text(fixtures_dir: Path):
    """Load UTF-8 fixture text by relative path under tests/fixtures."""

    def _read(relative_path: str) -> str:
        return (fixtures_dir / relative_path).read_text(encoding="utf-8")

    return _read


@pytest.fixture
def read_fixture_json(fixtures_dir: Path):
    """Load fixture JSON by relative path under tests/fixtures."""

    def _read(relative_path: str) -> dict[str, object]:
        return json.loads((fixtures_dir / relative_path).read_text(encoding="utf-8"))

    return _read
