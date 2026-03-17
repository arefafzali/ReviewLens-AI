"""API-level tests for ingestion orchestration routes."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Product, Workspace
from app.db.session import get_db_session


def _seed_workspace_and_product(session: Session) -> tuple[str, str]:
    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()

    session.add(Workspace(id=workspace_id, name="API Workspace"))
    session.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="capterra",
            name="API Product",
            source_url="https://www.capterra.com/p/api-product",
        )
    )
    session.commit()
    return str(workspace_id), str(product_id)


def test_ingestion_url_endpoint_returns_structured_result() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    seed_session = Session(engine)
    workspace_id, product_id = _seed_workspace_and_product(seed_session)
    seed_session.close()
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import create_app

    app = create_app()

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session

    with TestClient(app) as client:
        response = client.post(
            "/ingestion/url",
            json={
                "workspace_id": workspace_id,
                "product_id": product_id,
                "target_url": "https://www.capterra.com/p/api-product/reviews",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["outcome_code"] == "ok"
    assert payload["source_type"] == "scrape"
    assert payload["captured_reviews"] == 5
