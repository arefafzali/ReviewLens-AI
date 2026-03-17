"""Pytest bootstrap fixtures for backend tests."""

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture(autouse=True)
def set_test_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide mandatory environment values for tests."""

    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "test")


@pytest.fixture
def client() -> TestClient:
    """Return a test client with clean, test-scoped settings cache."""

    get_settings.cache_clear()
    from app.main import create_app

    app = create_app()
    test_client = TestClient(app)
    get_settings.cache_clear()
    return test_client
