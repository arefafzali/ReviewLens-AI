"""API tests for workspace/product context bootstrap endpoint."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Product, Workspace
from app.db.session import get_db_session


def test_context_ensure_creates_workspace_and_product() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
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

    workspace_uuid = uuid.uuid4()
    product_uuid = uuid.uuid4()
    workspace_id = str(workspace_uuid)
    product_id = str(product_uuid)

    with TestClient(app) as client:
        response = client.post(
            "/context/ensure",
            json={
                "workspace_id": workspace_id,
                "product_id": product_id,
                "platform": "generic",
                "product_name": "CoverageBook",
                "source_url": "https://www.capterra.com/p/147795/Coveragebook-com/reviews/",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_workspace"] is True
    assert payload["created_product"] is True

    verify_session = Session(engine)
    assert verify_session.query(Workspace).filter(Workspace.id == workspace_uuid).count() == 1
    assert verify_session.query(Product).filter(Product.id == product_uuid).count() == 1
    verify_session.close()


def test_context_ensure_is_idempotent_for_existing_ids() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()
    seed = Session(engine)
    seed.add(Workspace(id=workspace_id, name="Existing"))
    seed.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="generic",
            name="Existing Product",
            source_url="https://example.com/reviews",
        )
    )
    seed.commit()
    seed.close()

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
            "/context/ensure",
            json={
                "workspace_id": str(workspace_id),
                "product_id": str(product_id),
                "platform": "generic",
                "source_url": "https://example.com/reviews",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created_workspace"] is False
    assert payload["created_product"] is False
