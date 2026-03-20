"""Workflow-level integration tests using realistic fixture data."""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.models import Product, Review, Workspace
from app.db.session import get_db_session
from app.llm.fake_provider import FakeLLMProvider
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import (
    CSVIngestionRequest,
    IngestionOutcomeCode,
    IngestionRunStatus,
    URLIngestionRequest,
)
from app.services.ingestion.url_pipeline import URLIngestionPipelineResult
from app.services.ingestion_service import IngestionOrchestrationService
from app.services.retrieval_service import ReviewRetrievalService

CAPTERRA_URL = "https://www.capterra.com/p/164876/PressPage/reviews/"


def _setup_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_workspace_and_product(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()

    db.add(Workspace(id=workspace_id, name="Workflow Workspace"))
    db.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="capterra",
            name="Presspage",
            source_url=CAPTERRA_URL,
        )
    )
    db.commit()
    return workspace_id, product_id


def _parse_sse_events(body: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    event_name: str | None = None
    data_text: str | None = None

    for line in body.splitlines():
        line = line.strip("\r")
        if line.startswith("event:"):
            if event_name is not None and data_text is not None:
                events.append({"event": event_name, "data": json.loads(data_text)})
            event_name = line.split(":", 1)[1].strip()
            data_text = None
        elif line.startswith("data:"):
            data_text = line.split(":", 1)[1].strip()

    if event_name is not None and data_text is not None:
        events.append({"event": event_name, "data": json.loads(data_text)})

    return events


class _FixturePipeline:
    def __init__(self, extracted_reviews: list[dict[str, object]]) -> None:
        self._extracted_reviews = extracted_reviews

    def run(self, _: str) -> URLIngestionPipelineResult:
        return URLIngestionPipelineResult(
            status=IngestionRunStatus.SUCCESS,
            outcome_code=IngestionOutcomeCode.OK,
            captured_reviews=len(self._extracted_reviews),
            message="Ingestion completed successfully.",
            warnings=[],
            error_detail=None,
            diagnostics={"provider": "firecrawl", "source_host": "www.capterra.com"},
            extracted_reviews=self._extracted_reviews,
        )


def test_url_ingestion_fixture_flow_covers_dedupe_analytics_and_retrieval(monkeypatch, read_fixture_json) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)

    extracted_payload = read_fixture_json("json/capterra_extracted_reviews_sample.json")
    extracted_reviews = list(extracted_payload["reviews"])

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: _FixturePipeline(extracted_reviews),
    )

    service = IngestionOrchestrationService(IngestionRunRepository(db))
    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_URL,
            reload=True,
        )
    )

    assert result.status == IngestionRunStatus.SUCCESS
    assert result.outcome_code == IngestionOutcomeCode.OK
    assert result.captured_reviews == 3
    assert result.diagnostics["persisted_reviews"] == 3
    assert result.diagnostics["duplicates_removed"] == 1
    assert result.summary_snapshot["total_reviews"] == 3
    assert len(result.summary_snapshot["suggested_questions"]) >= 4

    retrieval = ReviewRetrievalService(db)
    matches = retrieval.retrieve_top_reviews(
        workspace_id=workspace_id,
        product_id=product_id,
        query="onboarding support automation",
        limit=5,
    )

    assert len(matches) >= 2
    assert any("onboarding" in item.body.lower() for item in matches)
    assert all(item.rank > 0 for item in matches)


def test_csv_ingestion_fixture_flow_covers_aliases_and_dedup(read_fixture_text) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)

    service = IngestionOrchestrationService(IngestionRunRepository(db))
    result = service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            source_ref="https://fixture.local/capterra-upload.csv",
            csv_content=read_fixture_text("csv/capterra_presspage_reviews_sample.csv"),
        )
    )

    assert result.status == IngestionRunStatus.SUCCESS
    assert result.outcome_code == IngestionOutcomeCode.OK
    assert result.captured_reviews == 3
    assert result.diagnostics["parser"] == "csv_alias_mapping"
    assert result.diagnostics["parsed_reviews"] == 4
    assert result.diagnostics["persisted_reviews"] == 3
    assert result.diagnostics["duplicates_removed"] == 1
    assert result.summary_snapshot["total_reviews"] == 3

    stored = db.query(Review).filter(Review.workspace_id == workspace_id, Review.product_id == product_id).all()
    assert len(stored) == 3


def test_chat_stream_endpoint_with_fake_provider_uses_fixture_seeded_reviews(monkeypatch, read_fixture_text) -> None:
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

    seed_db = Session(engine)
    workspace_id, product_id = _seed_workspace_and_product(seed_db)
    service = IngestionOrchestrationService(IngestionRunRepository(seed_db))
    service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            source_ref="https://fixture.local/capterra-upload.csv",
            csv_content=read_fixture_text("csv/capterra_presspage_reviews_sample.csv"),
        )
    )
    seed_db.close()

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(chat_response="Reviewers consistently praise onboarding speed and support quality."),
    )

    with TestClient(app) as client:
        client.cookies.set(get_settings().workspace_cookie_name, str(workspace_id))
        response = client.post(
            "/chat/stream",
            json={
                "product_id": str(product_id),
                "question": "What patterns do reviewers report about onboarding and support?",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("content-type", "").startswith("text/event-stream")

    events = _parse_sse_events(response.text)
    event_names = [item["event"] for item in events]

    assert "meta" in event_names
    assert "citations" in event_names
    assert "token" in event_names
    assert "done" in event_names

    done_event = next(item for item in events if item["event"] == "done")
    citations_event = next(item for item in events if item["event"] == "citations")
    assert done_event["data"]["classification"] == "answer"
    assert len(citations_event["data"]["items"]) >= 1
    assert "onboarding" in done_event["data"]["answer"].lower()
