"""Grounded starter question generation for ingested review datasets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.services.ingestion.review_analytics import ReviewAnalyticsRow


class SuggestedQuestionGenerator(Protocol):
    """Provider-agnostic interface for starter question generation."""

    def generate_questions(self, *, analytics: dict[str, Any], rows: list[ReviewAnalyticsRow]) -> list[str]:
        """Return grounded starter questions for the current dataset."""


@dataclass(frozen=True)
class DeterministicSuggestedQuestionGenerator:
    """Deterministic fallback generator suitable for production defaults and tests."""

    max_questions: int = 5

    def generate_questions(self, *, analytics: dict[str, Any], rows: list[ReviewAnalyticsRow]) -> list[str]:
        total_reviews = int(analytics.get("total_reviews", 0) or 0)
        if total_reviews <= 0 or not rows:
            return []

        keywords = _top_keyword_values(analytics)
        date_range = analytics.get("date_range") if isinstance(analytics.get("date_range"), dict) else {}
        start_date = date_range.get("start") if isinstance(date_range, dict) else None
        end_date = date_range.get("end") if isinstance(date_range, dict) else None

        histogram = analytics.get("rating_histogram") if isinstance(analytics.get("rating_histogram"), dict) else {}
        low_rated = int((histogram.get("1") or 0) + (histogram.get("2") or 0))
        high_rated = int((histogram.get("4") or 0) + (histogram.get("5") or 0))

        questions: list[str] = []

        questions.append(
            "Which themes appear most often across these "
            f"{total_reviews} reviews, and how consistently are they mentioned?"
        )

        if keywords:
            keyword_phrase = ", ".join(keywords[:3])
            questions.append(
                f"What specific feedback do reviewers give about {keyword_phrase}?"
            )
        else:
            questions.append(
                "What recurring strengths and weaknesses are visible in the review text?"
            )

        average_rating = analytics.get("average_rating")
        if isinstance(average_rating, (int, float)):
            questions.append(
                f"What reasons in the reviews best explain the {average_rating:.2f}/5 average rating?"
            )

        if low_rated > 0:
            questions.append(
                f"What are the most common concerns in the {low_rated} low-rated (1-2 star) reviews?"
            )
        elif high_rated > 0:
            questions.append(
                f"What strengths are most often cited in the {high_rated} high-rated (4-5 star) reviews?"
            )

        if start_date and end_date and start_date != end_date:
            questions.append(
                f"How did reviewer feedback change between {start_date} and {end_date}?"
            )
        else:
            questions.append(
                "Are there notable differences between recent reviews and older feedback in this dataset?"
            )

        questions.append("Which representative reviews best capture the main positive and negative viewpoints?")

        deduped = _dedupe_preserve_order(questions)
        minimum = 4 if total_reviews >= 2 else 2
        if len(deduped) < minimum:
            deduped.append("What follow-up questions should we ask to validate these findings in the current reviews?")
            deduped = _dedupe_preserve_order(deduped)

        return deduped[: self.max_questions]


def _top_keyword_values(analytics: dict[str, Any]) -> list[str]:
    raw_keywords = analytics.get("top_keywords")
    if not isinstance(raw_keywords, list):
        return []

    values: list[str] = []
    for item in raw_keywords:
        if not isinstance(item, dict):
            continue
        value = item.get("keyword")
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned:
                values.append(cleaned)
    return values


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in values:
        normalized = item.strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output
