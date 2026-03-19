"""Tests for product-scoped review retrieval behavior."""

from __future__ import annotations

from datetime import date
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Product, Review, Workspace
from app.services.retrieval_service import ReviewRetrievalService, _build_relaxed_or_tsquery


def _setup_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_workspace_and_products(db: Session) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    product_a = uuid.uuid4()
    product_b = uuid.uuid4()

    db.add(Workspace(id=workspace_id, name="Retrieval Workspace"))
    db.add(
        Product(
            id=product_a,
            workspace_id=workspace_id,
            platform="generic",
            name="Product A",
            source_url="https://example.com/a/reviews",
        )
    )
    db.add(
        Product(
            id=product_b,
            workspace_id=workspace_id,
            platform="generic",
            name="Product B",
            source_url="https://example.com/b/reviews",
        )
    )
    db.commit()
    return workspace_id, product_a, product_b


def test_retrieval_returns_top_relevant_reviews_scoped_to_product() -> None:
    db = _setup_db()
    workspace_id, product_a, product_b = _seed_workspace_and_products(db)

    db.add_all(
        [
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="a1",
                title="Excellent customer support",
                body="Customer support and onboarding are excellent for our team.",
                rating=4.8,
                reviewed_at=date(2026, 3, 1),
            ),
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="a2",
                title="Good overall",
                body="Solid analytics and dashboards, but onboarding is slower.",
                rating=4.0,
                reviewed_at=date(2026, 3, 2),
            ),
            Review(
                workspace_id=workspace_id,
                product_id=product_b,
                source_platform="generic",
                review_fingerprint="b1",
                title="Different product",
                body="Customer support is fast for product B only.",
                rating=5.0,
                reviewed_at=date(2026, 3, 3),
            ),
        ]
    )
    db.commit()

    service = ReviewRetrievalService(db)
    results = service.retrieve_top_reviews(
        workspace_id=workspace_id,
        product_id=product_a,
        query="support onboarding",
        limit=5,
    )

    assert len(results) == 2
    assert all(item.review_id is not None for item in results)
    assert "customer support" in results[0].body.lower()
    assert all("product b" not in item.body.lower() for item in results)


def test_retrieval_phrase_query_prioritizes_exact_phrase() -> None:
    db = _setup_db()
    workspace_id, product_a, _ = _seed_workspace_and_products(db)

    db.add_all(
        [
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="p1",
                title="Exact phrase",
                body="The customer support team resolved issues in one hour.",
                rating=5.0,
                reviewed_at=date(2026, 3, 1),
            ),
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="p2",
                title="Separated words",
                body="Our customers are happy and support docs are clear.",
                rating=4.0,
                reviewed_at=date(2026, 3, 2),
            ),
        ]
    )
    db.commit()

    service = ReviewRetrievalService(db)
    results = service.retrieve_top_reviews(
        workspace_id=workspace_id,
        product_id=product_a,
        query='"customer support"',
        limit=5,
    )

    assert len(results) == 1
    assert "customer support" in results[0].body.lower()


def test_retrieval_empty_query_returns_empty_list() -> None:
    db = _setup_db()
    workspace_id, product_a, _ = _seed_workspace_and_products(db)

    service = ReviewRetrievalService(db)
    results = service.retrieve_top_reviews(
        workspace_id=workspace_id,
        product_id=product_a,
        query="   ",
        limit=5,
    )

    assert results == []


def test_retrieval_returns_recent_reviews_for_broad_query_without_keyword_hits() -> None:
    db = _setup_db()
    workspace_id, product_a, _ = _seed_workspace_and_products(db)

    db.add_all(
        [
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="broad1",
                title="Great experience",
                body="Helpful team and easy setup.",
                rating=5.0,
                reviewed_at=date(2026, 3, 3),
            ),
            Review(
                workspace_id=workspace_id,
                product_id=product_a,
                source_platform="generic",
                review_fingerprint="broad2",
                title="Useful platform",
                body="Strong newsroom workflow capabilities.",
                rating=4.0,
                reviewed_at=date(2026, 3, 1),
            ),
        ]
    )
    db.commit()

    service = ReviewRetrievalService(db)
    results = service.retrieve_top_reviews(
        workspace_id=workspace_id,
        product_id=product_a,
        query="which themes are most consistent across reviews",
        limit=5,
    )

    assert len(results) == 2
    assert results[0].rank == 0.1
    assert results[0].reviewed_at == date(2026, 3, 3)


def test_relaxed_or_tsquery_builder_dedupes_and_caps_terms() -> None:
    query = "Support onboarding team team easy easy support analytics workflow reliability pricing"

    tsquery = _build_relaxed_or_tsquery(query, max_terms=5)

    assert tsquery == "support:* | onboarding:* | team:* | easy:* | analytics:*"


def test_relaxed_or_tsquery_builder_returns_none_without_keywords() -> None:
    assert _build_relaxed_or_tsquery('"" ""', max_terms=5) is None
