"""Tests for deterministic lightweight ingestion analytics generation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from app.services.ingestion.review_analytics import ReviewAnalyticsRow, compute_ingestion_analytics


def test_compute_ingestion_analytics_realistic_dataset() -> None:
    rows = [
        ReviewAnalyticsRow(
            title="Great onboarding",
            body="Onboarding and support were excellent and fast",
            rating=Decimal("5.00"),
            author_name="A",
            reviewed_at=date(2026, 3, 1),
            source_review_id="r1",
            review_fingerprint="f1",
            created_at=datetime(2026, 3, 10),
        ),
        ReviewAnalyticsRow(
            title="Solid workflow",
            body="Workflow improved for communications team",
            rating=Decimal("4.00"),
            author_name="B",
            reviewed_at=date(2026, 3, 1),
            source_review_id="r2",
            review_fingerprint="f2",
            created_at=datetime(2026, 3, 11),
        ),
        ReviewAnalyticsRow(
            title=None,
            body="Support team resolved issues quickly",
            rating=Decimal("3.00"),
            author_name=None,
            reviewed_at=date(2026, 3, 2),
            source_review_id=None,
            review_fingerprint="f3",
            created_at=datetime(2026, 3, 12),
        ),
    ]

    summary = compute_ingestion_analytics(rows)

    assert summary["total_reviews"] == 3
    assert summary["rated_reviews"] == 3
    assert summary["average_rating"] == 4.0
    assert summary["rating_histogram"] == {"1": 0, "2": 0, "3": 1, "4": 1, "5": 1}
    assert summary["date_range"] == {"start": "2026-03-01", "end": "2026-03-02"}
    assert summary["review_count_over_time"] == [
        {"date": "2026-03-01", "count": 2},
        {"date": "2026-03-02", "count": 1},
    ]
    keyword_counts = {item["keyword"]: item["count"] for item in summary["top_keywords"]}
    assert keyword_counts["support"] == 2
    assert len(summary["sample_review_previews"]) == 3


def test_compute_ingestion_analytics_sparse_dataset_is_graceful() -> None:
    rows = [
        ReviewAnalyticsRow(
            title=None,
            body="Only text with no numeric fields",
            rating=None,
            author_name=None,
            reviewed_at=None,
            source_review_id=None,
            review_fingerprint="f1",
            created_at=datetime(2026, 3, 10),
        )
    ]

    summary = compute_ingestion_analytics(rows)

    assert summary["average_rating"] is None
    assert summary["rated_reviews"] == 0
    assert summary["date_range"] == {"start": None, "end": None}
    assert summary["review_count_over_time"] == []
    assert summary["rating_histogram"] == {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}


def test_compute_ingestion_analytics_time_series_stable_sorting() -> None:
    rows = [
        ReviewAnalyticsRow(
            title="A",
            body="body",
            rating=Decimal("4.0"),
            author_name=None,
            reviewed_at=date(2026, 3, 3),
            source_review_id="r3",
            review_fingerprint="f3",
            created_at=datetime(2026, 3, 13),
        ),
        ReviewAnalyticsRow(
            title="B",
            body="body",
            rating=Decimal("4.0"),
            author_name=None,
            reviewed_at=date(2026, 3, 1),
            source_review_id="r1",
            review_fingerprint="f1",
            created_at=datetime(2026, 3, 11),
        ),
    ]

    summary = compute_ingestion_analytics(rows)
    assert [item["date"] for item in summary["review_count_over_time"]] == ["2026-03-01", "2026-03-03"]
