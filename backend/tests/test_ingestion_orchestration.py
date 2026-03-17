"""Tests for ingestion orchestration state transitions and result contracts."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Product, Workspace
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import CSVIngestionRequest, URLIngestionRequest
from app.services.ingestion_service import IngestionOrchestrationService


def _setup_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_workspace_and_product(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()

    db.add(
        Workspace(
            id=workspace_id,
            name="Test Workspace",
        )
    )
    db.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="capterra",
            name="Test Product",
            source_url="https://www.capterra.com/p/test-product",
        )
    )
    db.commit()
    return workspace_id, product_id


def test_url_ingestion_success_persists_final_state() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url="https://www.capterra.com/p/sample-product/reviews",
        )
    )

    assert result.status.value == "success"
    assert result.outcome_code.value == "ok"
    assert result.captured_reviews == 5
    assert result.completed_at is not None


def test_url_ingestion_partial_low_data_is_modeled() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url="https://www.capterra.com/p/sample-product/reviews?mode=low-data",
        )
    )

    assert result.status.value == "partial"
    assert result.outcome_code.value == "low_data"
    assert result.captured_reviews == 1
    assert result.warnings


def test_csv_ingestion_failure_empty_csv_is_persisted() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    result = service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            csv_filename="reviews.csv",
            csv_content="   ",
        )
    )

    assert result.status.value == "failed"
    assert result.outcome_code.value == "empty_csv"
    assert result.captured_reviews == 0
    assert result.completed_at is not None
