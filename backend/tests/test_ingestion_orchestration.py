"""Tests for ingestion orchestration state transitions and result contracts."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import IngestionRun, Product, Review, Workspace
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import (
    CSVIngestionRequest,
    IngestionOutcomeCode,
    IngestionRunStatus,
    IngestionSourceType,
    URLIngestionRequest,
)
from app.services.ingestion_service import IngestionOrchestrationService
from app.services.ingestion.url_pipeline import URLIngestionPipelineResult

CAPTERRA_PRESSPAGE_REVIEWS_URL = "https://www.capterra.com/p/164876/PressPage/reviews/"


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


class _FakePipeline:
    def __init__(self, result: URLIngestionPipelineResult) -> None:
        self._result = result

    def run(self, _: str) -> URLIngestionPipelineResult:
        return self._result


class _FixedQuestionGenerator:
    def generate_questions(self, *, analytics, rows):
        return [
            "What are users saying about onboarding speed?",
            "Which concerns appear in lower-rated reviews?",
            "How did sentiment evolve over time?",
            "Which review snippets best represent overall sentiment?",
        ]


def test_url_ingestion_success_persists_final_state(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: _FakePipeline(
            URLIngestionPipelineResult(
                status=IngestionRunStatus.SUCCESS,
                outcome_code=IngestionOutcomeCode.OK,
                captured_reviews=5,
                message="Ingestion completed successfully.",
                warnings=[],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source": "capterra"},
            )
        ),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        )
    )

    assert result.status.value == "success"
    assert result.outcome_code.value == "ok"
    assert result.captured_reviews == 5
    assert result.message == "Ingestion completed successfully."
    assert result.warnings == []
    assert result.diagnostics["provider"] == "firecrawl"
    assert result.ingestion_run_id
    assert result.started_at is not None
    assert result.completed_at is not None


def test_url_ingestion_partial_low_data_is_modeled(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: _FakePipeline(
            URLIngestionPipelineResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=1,
                message="Ingestion completed with limited captured reviews.",
                warnings=["Low review count detected."],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source": "capterra"},
            )
        ),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        )
    )

    assert result.status.value == "partial"
    assert result.outcome_code.value == "low_data"
    assert result.captured_reviews == 1
    assert "limited captured reviews" in result.message.lower()
    assert result.warnings
    assert result.diagnostics["source"] == "capterra"
    assert result.ingestion_run_id
    assert result.started_at is not None
    assert result.completed_at is not None


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


def test_csv_ingestion_parses_aliases_and_persists_reviews() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    csv_content = """Review Text,Stars,Reviewer Name,Headline,Reviewed At
Excellent support and workflow improvements,4.5,Sam R,Great product,2026-03-01
Solid feature set for teams,4,Ana T,Useful,2026-03-02
"""

    result = service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            csv_filename="reviews.csv",
            csv_content=csv_content,
        )
    )

    stored_reviews = db.query(Review).all()
    assert result.status.value == "success"
    assert result.outcome_code.value == "ok"
    assert result.captured_reviews == 2
    assert result.diagnostics["parser"] == "csv_alias_mapping"
    assert result.diagnostics["persisted_reviews"] == 2
    assert result.diagnostics["duplicates_removed"] == 0
    assert result.diagnostics["analytics_generated"] is True
    assert len(stored_reviews) == 2

    product = db.query(Product).filter(Product.id == product_id).one()
    run = db.query(IngestionRun).filter(IngestionRun.id == result.ingestion_run_id).one()
    assert product.stats["total_reviews"] == 2
    assert "rating_histogram" in product.stats
    assert len(product.stats["suggested_questions"]) >= 4
    assert all(isinstance(item, str) and item for item in product.stats["suggested_questions"])
    assert run.summary_snapshot["total_reviews"] == 2
    assert run.summary_snapshot["review_count_over_time"][0]["date"] == "2026-03-01"
    assert len(run.summary_snapshot["suggested_questions"]) >= 4


def test_csv_ingestion_malformed_rows_are_explicit_failure() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    malformed_csv = """body,rating,author
Works well,5,Sam,unexpected
"""

    result = service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            csv_filename="broken.csv",
            csv_content=malformed_csv,
        )
    )

    assert result.status.value == "failed"
    assert result.outcome_code.value == "malformed_csv"
    assert result.captured_reviews == 0


def test_url_ingestion_persists_extracted_reviews_rows(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: _FakePipeline(
            URLIngestionPipelineResult(
                status=IngestionRunStatus.SUCCESS,
                outcome_code=IngestionOutcomeCode.OK,
                captured_reviews=2,
                message="Ingestion completed successfully.",
                warnings=[],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source_host": "www.capterra.com"},
                extracted_reviews=[
                    {
                        "title": "Great",
                        "body": "This product was very helpful for our team.",
                        "rating": "4.5",
                        "author": "Alex",
                        "date": "2026-03-01",
                        "url": "https://example.com/review/1",
                    },
                    {
                        "title": "Great",
                        "body": "This product was very helpful for our team.",
                        "rating": "4.5",
                        "author": "Alex",
                        "date": "2026-03-01",
                        "url": "https://example.com/review/1",
                    },
                    {
                        "title": "Solid",
                        "body": "Support has been responsive and onboarding was smooth.",
                        "rating": "4",
                        "author": "Mina",
                        "date": "2026-02-17",
                        "url": "https://example.com/review/2",
                    },
                ],
            )
        ),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        )
    )

    stored_reviews = db.query(Review).all()
    assert len(stored_reviews) == 2
    assert result.captured_reviews == 2
    assert result.diagnostics["persisted_reviews"] == 2
    assert result.diagnostics["extracted_reviews"] == 2
    assert result.diagnostics["duplicates_removed"] == 1


def test_url_ingestion_uses_cache_when_reviews_already_stored(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    repository = IngestionRunRepository(db)
    service = IngestionOrchestrationService(repository)

    previous_run = repository.create_attempt(
        workspace_id=workspace_id,
        product_id=product_id,
        source_type=IngestionSourceType.SCRAPE,
        target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        csv_filename=None,
    )
    inserted = repository.persist_extracted_reviews(
        workspace_id=workspace_id,
        product_id=product_id,
        ingestion_run_id=previous_run.id,
        source_host="www.capterra.com",
        reviews=[
            {
                "title": "Great",
                "body": "Very useful and reliable platform for our comms team.",
                "rating": "5",
                "author": "Jess",
                "date": "2026-03-01",
                "url": "https://example.com/review/a",
            }
        ],
    )
    assert inserted.inserted_reviews == 1
    repository.finalize_attempt(
        run=previous_run,
        status=IngestionRunStatus.SUCCESS,
        outcome_code=IngestionOutcomeCode.OK,
        captured_reviews=1,
        message="Ingestion completed successfully.",
        warnings=[],
        diagnostics={"provider": "firecrawl", "source_host": "www.capterra.com", "parser": "gpt_markdown_chunks"},
    )

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: (_ for _ in ()).throw(AssertionError("pipeline should not be called on cache hit")),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        )
    )

    assert result.status == IngestionRunStatus.SUCCESS
    assert result.outcome_code == IngestionOutcomeCode.OK
    assert result.captured_reviews == 1
    assert result.diagnostics["cache_hit"] is True
    assert result.diagnostics["cached_reviews"] == 1


def test_url_ingestion_reload_bypasses_cache_and_reextracts(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    repository = IngestionRunRepository(db)
    service = IngestionOrchestrationService(repository)

    previous_run = repository.create_attempt(
        workspace_id=workspace_id,
        product_id=product_id,
        source_type=IngestionSourceType.SCRAPE,
        target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        csv_filename=None,
    )
    repository.persist_extracted_reviews(
        workspace_id=workspace_id,
        product_id=product_id,
        ingestion_run_id=previous_run.id,
        source_host="www.capterra.com",
        reviews=[
            {
                "title": "Cached",
                "body": "Cached review body.",
                "rating": "4",
                "author": "Cache User",
                "date": "2026-03-01",
                "url": "https://example.com/review/cache",
            }
        ],
    )
    repository.finalize_attempt(
        run=previous_run,
        status=IngestionRunStatus.SUCCESS,
        outcome_code=IngestionOutcomeCode.OK,
        captured_reviews=1,
        message="Ingestion completed successfully.",
        warnings=[],
        diagnostics={"provider": "firecrawl", "source_host": "www.capterra.com", "parser": "gpt_markdown_chunks"},
    )

    monkeypatch.setattr(
        "app.services.ingestion_service.URLIngestionPipeline.with_firecrawl",
        lambda **_: _FakePipeline(
            URLIngestionPipelineResult(
                status=IngestionRunStatus.SUCCESS,
                outcome_code=IngestionOutcomeCode.OK,
                captured_reviews=1,
                message="Ingestion completed successfully.",
                warnings=[],
                error_detail=None,
                diagnostics={"provider": "firecrawl", "source_host": "www.capterra.com", "parser": "gpt_markdown_chunks"},
                extracted_reviews=[
                    {
                        "title": "Fresh",
                        "body": "Fresh review body from reload path.",
                        "rating": "5",
                        "author": "Reload User",
                        "date": "2026-03-02",
                        "url": "https://example.com/review/fresh",
                    }
                ],
            )
        ),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
            reload=True,
        )
    )

    assert result.status == IngestionRunStatus.SUCCESS
    assert result.outcome_code == IngestionOutcomeCode.OK
    assert result.captured_reviews == 1
    assert result.diagnostics["cache_hit"] is False
    assert result.diagnostics["reload"] is True


def test_csv_ingestion_persists_injected_suggested_questions() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    repository = IngestionRunRepository(db, suggested_question_generator=_FixedQuestionGenerator())
    service = IngestionOrchestrationService(repository)

    csv_content = """body,rating,author,date
Great onboarding and support,5,Sam,2026-03-01
Reporting needs improvement,2,Ana,2026-03-02
"""

    result = service.attempt_csv_ingestion(
        CSVIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            csv_filename="reviews.csv",
            csv_content=csv_content,
        )
    )

    run = db.query(IngestionRun).filter(IngestionRun.id == result.ingestion_run_id).one()
    product = db.query(Product).filter(Product.id == product_id).one()

    expected = [
        "What are users saying about onboarding speed?",
        "Which concerns appear in lower-rated reviews?",
        "How did sentiment evolve over time?",
        "Which review snippets best represent overall sentiment?",
    ]
    assert run.summary_snapshot["suggested_questions"] == expected
    assert product.stats["suggested_questions"] == expected


def test_url_ingestion_invalid_llm_provider_config_is_modeled(monkeypatch) -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_workspace_and_product(db)
    service = IngestionOrchestrationService(IngestionRunRepository(db))

    monkeypatch.setattr(
        "app.services.ingestion_service.build_llm_provider",
        lambda *_: (_ for _ in ()).throw(ValueError("Unsupported LLM provider: unknown")),
    )

    result = service.attempt_url_ingestion(
        URLIngestionRequest(
            workspace_id=workspace_id,
            product_id=product_id,
            target_url=CAPTERRA_PRESSPAGE_REVIEWS_URL,
        )
    )

    assert result.status == IngestionRunStatus.FAILED
    assert result.outcome_code == IngestionOutcomeCode.PARSE_FAILED
    assert result.message == "Configured LLM provider is invalid."
    assert result.diagnostics["failure_stage"] == "llm_provider_config"
