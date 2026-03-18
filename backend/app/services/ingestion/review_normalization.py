"""Normalization and deterministic deduping helpers for ingested reviews."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class NormalizedReviewRecord:
    """Normalized review payload used by repository persistence logic."""

    title: str | None
    body: str
    rating: Decimal | None
    author_name: str | None
    reviewed_at: date | None
    source_review_id: str | None
    review_fingerprint: str
    raw_payload: dict[str, Any]


@dataclass(frozen=True)
class NormalizationResult:
    """Normalization output with dedupe/validation counters."""

    normalized_reviews: list[NormalizedReviewRecord]
    duplicates_in_payload: int
    skipped_missing_body: int


def normalize_reviews_for_persistence(
    *,
    platform: str,
    reviews: list[dict[str, Any]],
) -> NormalizationResult:
    """Normalize incoming parsed review rows and dedupe within a payload batch."""

    normalized_records: list[NormalizedReviewRecord] = []
    duplicates_in_payload = 0
    skipped_missing_body = 0
    seen_fingerprints: set[str] = set()

    for raw in reviews:
        body = _safe_text(raw.get("body"))
        if not body:
            skipped_missing_body += 1
            continue

        title = _safe_text(raw.get("title"))
        author_name = _safe_text(raw.get("author"))
        rating = _safe_rating(raw.get("rating"))
        reviewed_at = _safe_review_date(raw.get("date"))
        source_review_id = _extract_external_review_id(raw)

        fingerprint = _review_fingerprint(
            platform=platform,
            source_review_id=source_review_id,
            title=title,
            body=body,
            author=author_name,
            reviewed_at=reviewed_at,
            rating=rating,
        )

        if fingerprint in seen_fingerprints:
            duplicates_in_payload += 1
            continue
        seen_fingerprints.add(fingerprint)

        normalized_records.append(
            NormalizedReviewRecord(
                title=title,
                body=body,
                rating=rating,
                author_name=author_name,
                reviewed_at=reviewed_at,
                source_review_id=source_review_id,
                review_fingerprint=fingerprint,
                raw_payload=dict(raw),
            )
        )

    return NormalizationResult(
        normalized_reviews=normalized_records,
        duplicates_in_payload=duplicates_in_payload,
        skipped_missing_body=skipped_missing_body,
    )


def _extract_external_review_id(payload: dict[str, Any]) -> str | None:
    for key in [
        "external_review_id",
        "externalReviewId",
        "source_review_id",
        "sourceReviewId",
        "review_id",
        "reviewId",
        "id",
        "url",
        "review_url",
        "reviewUrl",
        "link",
    ]:
        value = _safe_text(payload.get(key))
        if value:
            return value[:255]
    return None


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    return normalized or None


def _safe_rating(value: Any) -> Decimal | None:
    text = _safe_text(value)
    if not text:
        return None

    try:
        numeric = Decimal(text)
    except (ArithmeticError, ValueError):
        return None

    if numeric < 0 or numeric > 5:
        return None

    return numeric.quantize(Decimal("0.01"))


def _safe_review_date(value: Any) -> date | None:
    text = _safe_text(value)
    if not text:
        return None

    candidates = [text]
    if " on " in text.lower():
        candidates.append(text.split(" on ")[-1].strip())

    for candidate in candidates:
        iso_candidate = candidate.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso_candidate).date()
        except ValueError:
            pass

        for pattern in ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                return datetime.strptime(candidate, pattern).date()
            except ValueError:
                continue

    return None


def _review_fingerprint(
    *,
    platform: str,
    source_review_id: str | None,
    title: str | None,
    body: str,
    author: str | None,
    reviewed_at: date | None,
    rating: Decimal | None,
) -> str:
    # Prefer stable external ID when present; fallback to normalized content signature.
    if source_review_id:
        signature = "|".join([platform, "ext", source_review_id.strip().lower()])
    else:
        signature = "|".join(
            [
                platform,
                "content",
                (title or "").strip().lower(),
                body.strip().lower(),
                (author or "").strip().lower(),
                reviewed_at.isoformat() if reviewed_at else "",
                str(rating) if rating is not None else "",
            ]
        )
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()
