"""Tests for review normalization and deterministic dedupe hashing."""

from __future__ import annotations

from app.services.ingestion.review_normalization import normalize_reviews_for_persistence


def test_normalization_is_deterministic_for_same_payload() -> None:
    payload = [
        {
            "title": "Great Product",
            "body": "Very useful for our team",
            "rating": "4.5",
            "author": "Alex",
            "date": "2026-03-01",
            "url": "https://example.com/reviews/123",
        }
    ]

    result_a = normalize_reviews_for_persistence(platform="capterra", reviews=payload)
    result_b = normalize_reviews_for_persistence(platform="capterra", reviews=payload)

    assert len(result_a.normalized_reviews) == 1
    assert result_a.normalized_reviews[0].review_fingerprint == result_b.normalized_reviews[0].review_fingerprint


def test_normalization_uses_external_id_for_dedupe_when_present() -> None:
    payload = [
        {
            "external_review_id": "R-100",
            "body": "Original text",
        },
        {
            "external_review_id": "R-100",
            "body": "Updated text but same review id",
        },
    ]

    result = normalize_reviews_for_persistence(platform="capterra", reviews=payload)

    assert len(result.normalized_reviews) == 1
    assert result.duplicates_in_payload == 1


def test_normalization_handles_missing_optional_fields() -> None:
    payload = [
        {
            "body": "Body exists",
            "rating": "not-a-number",
        },
        {
            "title": "No body should be skipped",
        },
    ]

    result = normalize_reviews_for_persistence(platform="capterra", reviews=payload)

    assert len(result.normalized_reviews) == 1
    record = result.normalized_reviews[0]
    assert record.title is None
    assert record.author_name is None
    assert record.reviewed_at is None
    assert record.rating is None
    assert result.skipped_missing_body == 1
