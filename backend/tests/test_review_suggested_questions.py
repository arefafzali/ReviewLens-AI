"""Tests for grounded starter question generation from ingestion analytics."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.services.ingestion.review_analytics import ReviewAnalyticsRow, compute_ingestion_analytics
from app.services.ingestion.review_suggested_questions import DeterministicSuggestedQuestionGenerator


def test_deterministic_generator_returns_grounded_questions() -> None:
    rows = [
        ReviewAnalyticsRow(
            title="Fast onboarding",
            body="Onboarding was quick and support responded in minutes.",
            rating=Decimal("5.00"),
            author_name="A",
            reviewed_at=date(2026, 3, 1),
            source_review_id="r1",
            review_fingerprint="f1",
            created_at=datetime(2026, 3, 10),
        ),
        ReviewAnalyticsRow(
            title="Needs better reporting",
            body="Reporting is limited but workflow tools are strong.",
            rating=Decimal("2.00"),
            author_name="B",
            reviewed_at=date(2026, 3, 4),
            source_review_id="r2",
            review_fingerprint="f2",
            created_at=datetime(2026, 3, 11),
        ),
    ]
    analytics = compute_ingestion_analytics(rows)

    questions = DeterministicSuggestedQuestionGenerator().generate_questions(analytics=analytics, rows=rows)

    assert len(questions) == 5
    assert any("support" in item.lower() or "onboarding" in item.lower() for item in questions)
    assert any("3.50/5" in item for item in questions)
    assert any("1-2 star" in item for item in questions)
    assert any("2026-03-01" in item and "2026-03-04" in item for item in questions)


def test_deterministic_generator_handles_empty_rows() -> None:
    questions = DeterministicSuggestedQuestionGenerator().generate_questions(analytics={"total_reviews": 0}, rows=[])
    assert questions == []


def test_deterministic_generator_sparse_dataset_minimum_questions() -> None:
    rows = [
        ReviewAnalyticsRow(
            title=None,
            body="Simple text feedback only",
            rating=None,
            author_name=None,
            reviewed_at=None,
            source_review_id="r1",
            review_fingerprint="f1",
            created_at=datetime(2026, 3, 10),
        )
    ]
    analytics = compute_ingestion_analytics(rows)

    questions = DeterministicSuggestedQuestionGenerator().generate_questions(analytics=analytics, rows=rows)

    assert len(questions) >= 2
    assert len(questions) <= 5
