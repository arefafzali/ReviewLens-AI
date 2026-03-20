"""Lightweight deterministic analytics computed from stored normalized reviews."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import re
from typing import Any

_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "were",
    "have",
    "has",
    "had",
    "our",
    "you",
    "your",
    "they",
    "their",
    "about",
    "into",
    "after",
    "before",
    "over",
    "under",
    "very",
    "more",
    "most",
    "just",
    "also",
    "not",
    "its",
    "it's",
    "can",
    "could",
    "would",
    "should",
    "review",
    "reviews",
    "product",
    "platform",
    "generic_source",
    "www",
    "http",
    "https",
    "com",
}

_TOKEN_RE = re.compile(r"[a-z]{3,}")


@dataclass(frozen=True)
class ReviewAnalyticsRow:
    title: str | None
    body: str
    rating: Decimal | None
    author_name: str | None
    reviewed_at: date | None
    source_review_id: str | None
    review_fingerprint: str
    created_at: datetime | None


def compute_ingestion_analytics(rows: list[ReviewAnalyticsRow]) -> dict[str, Any]:
    histogram = {str(star): 0 for star in range(1, 6)}
    ratings: list[Decimal] = []
    dated_counts: Counter[str] = Counter()
    keyword_counts: Counter[str] = Counter()

    dated_values: list[date] = []
    for row in rows:
        if row.rating is not None:
            ratings.append(row.rating)
            bucket = _rating_bucket(row.rating)
            histogram[str(bucket)] += 1

        if row.reviewed_at is not None:
            dated_values.append(row.reviewed_at)
            dated_counts[row.reviewed_at.isoformat()] += 1

        text = " ".join(part for part in [row.title or "", row.body or ""] if part)
        for token in _extract_keywords(text):
            keyword_counts[token] += 1

    average_rating: float | None = None
    if ratings:
        total = sum(ratings)
        average_rating = float((total / Decimal(len(ratings))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    top_keywords = [
        {"keyword": keyword, "count": count}
        for keyword, count in sorted(keyword_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    ]

    time_series = [
        {"date": day, "count": dated_counts[day]}
        for day in sorted(dated_counts.keys())
    ]

    sorted_rows = sorted(
        rows,
        key=lambda item: (
            item.reviewed_at is not None,
            item.reviewed_at or date.min,
            item.created_at or datetime.min,
            item.review_fingerprint,
        ),
        reverse=True,
    )
    sample_previews = []
    for row in sorted_rows[:5]:
        body_preview = (row.body or "")[:180]
        sample_previews.append(
            {
                "review_id": row.source_review_id or row.review_fingerprint,
                "title": row.title,
                "author": row.author_name,
                "rating": float(row.rating) if row.rating is not None else None,
                "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
                "body_preview": body_preview,
            }
        )

    date_range = {
        "start": min(dated_values).isoformat() if dated_values else None,
        "end": max(dated_values).isoformat() if dated_values else None,
    }

    return {
        "total_reviews": len(rows),
        "rated_reviews": len(ratings),
        "average_rating": average_rating,
        "rating_histogram": histogram,
        "review_count_over_time": time_series,
        "date_range": date_range,
        "top_keywords": top_keywords,
        "sample_review_previews": sample_previews,
    }


def _rating_bucket(value: Decimal) -> int:
    bucket = int(value.to_integral_value(rounding=ROUND_HALF_UP))
    return min(5, max(1, bucket))


def _extract_keywords(text: str) -> list[str]:
    tokens = [token for token in _TOKEN_RE.findall(text.lower()) if token not in _STOPWORDS]
    return tokens

