"""Security-oriented settings validation tests."""

from __future__ import annotations

import pytest

from app.config import Settings


def _set_base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "test")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")


def test_rejects_same_site_none_without_secure_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SAME_SITE", "none")
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SECURE", "false")

    with pytest.raises(ValueError, match="workspace_cookie_secure"):
        Settings()


def test_requires_secure_cookie_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "production")
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SECURE", "false")
    monkeypatch.setenv("REVIEWLENS_CORS_ALLOW_ORIGINS", '["https://reviewlens.example"]')

    with pytest.raises(ValueError, match="must be true in production"):
        Settings()


def test_rejects_wildcard_cors_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "production")
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SECURE", "true")
    monkeypatch.setenv("REVIEWLENS_CORS_ALLOW_ORIGINS", '["*"]')

    with pytest.raises(ValueError, match="cannot contain '\\*' in production"):
        Settings()


def test_allows_secure_production_cookie_and_explicit_cors(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_base_env(monkeypatch)
    monkeypatch.setenv("REVIEWLENS_ENVIRONMENT", "production")
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SECURE", "true")
    monkeypatch.setenv("REVIEWLENS_WORKSPACE_COOKIE_SAME_SITE", "lax")
    monkeypatch.setenv("REVIEWLENS_CORS_ALLOW_ORIGINS", '["https://reviewlens.example"]')

    settings = Settings()

    assert settings.environment == "production"
    assert settings.workspace_cookie_secure is True
