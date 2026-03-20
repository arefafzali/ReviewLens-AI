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
from app.config import get_settings
from app.schemas.ingestion import IngestionOutcomeCode, IngestionRunStatus
from app.services.ingestion.url_pipeline import URLIngestionPipelineResult

CAPTERRA_PRESSPAGE_REVIEWS_URL = "https://www.capterra.com/p/164876/PressPage/reviews/"


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

    class _FakePipeline:
        def run(self, _: str) -> URLIngestionPipelineResult:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.SUCCESS,
                outcome_code=IngestionOutcomeCode.OK,
                captured_reviews=5,
                message="Ingestion completed successfully.",
                warnings=[],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source": "capterra"},
            )

    app.dependency_overrides.clear()

    import app.services.ingestion_service as ingestion_service_module

    original_factory = ingestion_service_module.URLIngestionPipeline.with_firecrawl
    ingestion_service_module.URLIngestionPipeline.with_firecrawl = classmethod(lambda cls, **_: _FakePipeline())

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ingestion/url",
                json={
                    "workspace_id": workspace_id,
                    "product_id": product_id,
                    "target_url": CAPTERRA_PRESSPAGE_REVIEWS_URL,
                },
            )
    finally:
        ingestion_service_module.URLIngestionPipeline.with_firecrawl = original_factory

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["outcome_code"] == "ok"
    assert payload["source_type"] == "scrape"
    assert payload["captured_reviews"] == 5
    assert payload["warnings"] == []
    assert payload["diagnostics"]["provider"] == "firecrawl"
    assert payload["message"] == "Ingestion completed successfully."
    assert payload["ingestion_run_id"]
    assert payload["started_at"] is not None
    assert payload["completed_at"] is not None


def test_ingestion_url_endpoint_processes_unknown_host_with_chunk_extraction() -> None:
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

    class _FakePipeline:
        def run(self, _: str) -> URLIngestionPipelineResult:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=0,
                message="Ingestion completed but no review records were captured.",
                warnings=["No review cards were detected in fetched pages."],
                error_detail=None,
                diagnostics={"failure_stage": None, "source_host": "www.g2.com", "parser": "gpt_markdown_chunks"},
            )

    app.dependency_overrides.clear()

    import app.services.ingestion_service as ingestion_service_module

    original_factory = ingestion_service_module.URLIngestionPipeline.with_firecrawl
    ingestion_service_module.URLIngestionPipeline.with_firecrawl = classmethod(lambda cls, **_: _FakePipeline())

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/ingestion/url",
                json={
                    "workspace_id": workspace_id,
                    "product_id": product_id,
                    "target_url": "https://www.g2.com/products/example/reviews",
                },
            )
    finally:
        ingestion_service_module.URLIngestionPipeline.with_firecrawl = original_factory

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["outcome_code"] == "low_data"
    assert payload["captured_reviews"] == 0
    assert payload["diagnostics"]["failure_stage"] is None
    assert payload["diagnostics"]["source_host"] == "www.g2.com"


def test_ingestion_url_preflight_options_is_allowed() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    from app.main import create_app

    app = create_app()

    with TestClient(app) as client:
        response = client.options(
            "/ingestion/url",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_ingestion_url_endpoint_resolves_workspace_from_cookie() -> None:
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

    class _FakePipeline:
        def run(self, _: str) -> URLIngestionPipelineResult:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.SUCCESS,
                outcome_code=IngestionOutcomeCode.OK,
                captured_reviews=3,
                message="Ingestion completed successfully.",
                warnings=[],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source": "capterra"},
            )

    app.dependency_overrides.clear()

    import app.services.ingestion_service as ingestion_service_module

    original_factory = ingestion_service_module.URLIngestionPipeline.with_firecrawl
    ingestion_service_module.URLIngestionPipeline.with_firecrawl = classmethod(lambda cls, **_: _FakePipeline())

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session

    try:
        with TestClient(app) as client:
            client.cookies.set(get_settings().workspace_cookie_name, workspace_id)
            response = client.post(
                "/ingestion/url",
                json={
                    "product_id": product_id,
                    "target_url": CAPTERRA_PRESSPAGE_REVIEWS_URL,
                },
            )
    finally:
        ingestion_service_module.URLIngestionPipeline.with_firecrawl = original_factory

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["captured_reviews"] == 3
