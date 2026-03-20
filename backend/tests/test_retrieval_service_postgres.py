"""Postgres integration test for retrieval ranking parity.

This test is optional and runs only when a Postgres test URL is provided.
Set REVIEWLENS_POSTGRES_TEST_URL to enable in local/CI environments.
"""

from __future__ import annotations

from datetime import date
import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy import create_engine

from app.db.base import Base
from app.db.models import Product, Review, Workspace
from app.services.retrieval_service import ReviewRetrievalService


@pytest.mark.integration
def test_postgres_retrieval_prefers_phrase_match_and_scope() -> None:
    db_url = os.getenv("REVIEWLENS_POSTGRES_TEST_URL")
    if not db_url:
        pytest.skip("REVIEWLENS_POSTGRES_TEST_URL is not set.")

    engine = create_engine(db_url, future=True)
    if engine.dialect.name != "postgresql":
        pytest.skip("Configured REVIEWLENS_POSTGRES_TEST_URL is not PostgreSQL.")

    Base.metadata.create_all(engine)
    session = Session(engine)

    workspace_id = uuid.uuid4()
    product_a = uuid.uuid4()
    product_b = uuid.uuid4()

    try:
        session.add(Workspace(id=workspace_id, name="PG Retrieval Workspace"))
        session.add(
            Product(
                id=product_a,
                workspace_id=workspace_id,
                platform="capterra",
                name="Product A",
                source_url="https://example.com/a/reviews",
            )
        )
        session.add(
            Product(
                id=product_b,
                workspace_id=workspace_id,
                platform="capterra",
                name="Product B",
                source_url="https://example.com/b/reviews",
            )
        )

        session.add_all(
            [
                Review(
                    workspace_id=workspace_id,
                    product_id=product_a,
                    source_platform="capterra",
                    review_fingerprint=f"{workspace_id}-a1",
                    title="Exact phrase candidate",
                    body="Customer support and onboarding were excellent.",
                    rating=4.8,
                    reviewed_at=date(2026, 3, 1),
                ),
                Review(
                    workspace_id=workspace_id,
                    product_id=product_a,
                    source_platform="capterra",
                    review_fingerprint=f"{workspace_id}-a2",
                    title="Separated words",
                    body="Our customers are happy and support docs are clear.",
                    rating=4.0,
                    reviewed_at=date(2026, 3, 2),
                ),
                Review(
                    workspace_id=workspace_id,
                    product_id=product_b,
                    source_platform="capterra",
                    review_fingerprint=f"{workspace_id}-b1",
                    title="Other product",
                    body="Customer support themes for another product.",
                    rating=5.0,
                    reviewed_at=date(2026, 3, 3),
                ),
            ]
        )
        session.flush()

        session.execute(
            text(
                """
                UPDATE reviews
                SET search_vector = to_tsvector(
                    'english',
                    coalesce(title, '') || ' ' || coalesce(body, '')
                )
                WHERE workspace_id = :workspace_id
                """
            ),
            {"workspace_id": workspace_id},
        )
        session.commit()

        service = ReviewRetrievalService(session)
        results = service.retrieve_top_reviews(
            workspace_id=workspace_id,
            product_id=product_a,
            query='"customer support"',
            limit=5,
        )

        assert len(results) == 1
        assert "customer support" in results[0].body.lower()
        assert "another product" not in results[0].body.lower()
    finally:
        session.query(Review).filter(Review.workspace_id == workspace_id).delete()
        session.query(Product).filter(Product.workspace_id == workspace_id).delete()
        session.query(Workspace).filter(Workspace.id == workspace_id).delete()
        session.commit()
        session.close()
