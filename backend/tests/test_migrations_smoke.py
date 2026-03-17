"""Smoke test for Alembic baseline migration SQL generation."""

from __future__ import annotations

from alembic import command
from alembic.config import Config


def test_alembic_upgrade_head_sql_smoke(monkeypatch, capsys) -> None:
    """Ensure migration baseline renders expected SQL from an empty schema."""

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/reviewlens")

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head", sql=True)

    output = capsys.readouterr().out.lower()

    assert "create table workspaces" in output
    assert "create table products" in output
    assert "create table ingestion_runs" in output
    assert "create table reviews" in output
    assert "create table chat_sessions" in output
    assert "create table chat_messages" in output
    assert "create index ix_reviews_search_vector" in output
    assert "uq_reviews_source_review_id_not_null" in output
