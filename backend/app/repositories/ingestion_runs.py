"""Persistence helpers for ingestion run lifecycle."""

from __future__ import annotations

import hashlib
from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Review
from app.schemas.ingestion import IngestionOutcomeCode, IngestionRunStatus, IngestionSourceType


class IngestionRunRepository:
    """Encapsulates ingestion run create/finalize persistence operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create_attempt(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        source_type: IngestionSourceType,
        target_url: str | None,
        csv_filename: str | None,
    ) -> IngestionRun:
        now = datetime.now(timezone.utc)
        run = IngestionRun(
            workspace_id=workspace_id,
            product_id=product_id,
            source_type=source_type.value,
            status=IngestionRunStatus.RUNNING.value,
            target_url=target_url,
            csv_filename=csv_filename,
            started_at=now,
            created_at=now,
            updated_at=now,
            result_metadata={},
            records_ingested=0,
        )

        self._db.add(run)
        try:
            self._db.commit()
        except IntegrityError:
            self._db.rollback()
            raise

        self._db.refresh(run)
        return run

    def finalize_attempt(
        self,
        *,
        run: IngestionRun,
        status: IngestionRunStatus,
        outcome_code: IngestionOutcomeCode,
        captured_reviews: int,
        message: str,
        warnings: list[str] | None = None,
        error_detail: str | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> IngestionRun:
        now = datetime.now(timezone.utc)

        run.status = status.value
        run.outcome_code = outcome_code.value
        run.records_ingested = captured_reviews
        run.error_detail = error_detail
        run.result_metadata = {
            "message": message,
            "warnings": warnings or [],
            "diagnostics": diagnostics or {},
        }
        run.completed_at = now
        run.updated_at = now

        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)
        return run

    def persist_extracted_reviews(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        ingestion_run_id: UUID,
        source_host: str | None,
        reviews: list[dict[str, Any]],
    ) -> int:
        platform = _platform_from_host(source_host)

        normalized_rows: list[dict[str, Any]] = []
        for raw in reviews:
            body = _safe_text(raw.get("body"))
            if not body:
                continue

            title = _safe_text(raw.get("title"))
            author_name = _safe_text(raw.get("author"))
            source_review_id = _safe_text(raw.get("url"))
            rating = _safe_rating(raw.get("rating"))
            reviewed_at = _safe_review_date(raw.get("date"))
            fingerprint = _review_fingerprint(
                platform=platform,
                body=body,
                author=author_name,
                reviewed_at=reviewed_at,
                rating=rating,
            )

            normalized_rows.append(
                {
                    "title": title,
                    "body": body,
                    "author_name": author_name,
                    "source_review_id": source_review_id,
                    "rating": rating,
                    "reviewed_at": reviewed_at,
                    "review_fingerprint": fingerprint,
                    "metadata": {
                        "raw": dict(raw),
                    },
                }
            )

        if not normalized_rows:
            return 0

        incoming_fingerprints = {item["review_fingerprint"] for item in normalized_rows}
        existing_rows = (
            self._db.query(Review.review_fingerprint)
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
                Review.source_platform == platform,
                Review.review_fingerprint.in_(incoming_fingerprints),
            )
            .all()
        )
        existing_fingerprints = {row[0] for row in existing_rows}

        review_records: list[Review] = []
        seen_in_batch: set[str] = set()
        for row in normalized_rows:
            fingerprint = row["review_fingerprint"]
            if fingerprint in existing_fingerprints or fingerprint in seen_in_batch:
                continue
            seen_in_batch.add(fingerprint)
            review_records.append(
                Review(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    ingestion_run_id=ingestion_run_id,
                    source_platform=platform,
                    source_review_id=row["source_review_id"],
                    review_fingerprint=fingerprint,
                    title=row["title"],
                    body=row["body"],
                    rating=row["rating"],
                    reviewed_at=row["reviewed_at"],
                    author_name=row["author_name"],
                    language_code=None,
                    review_metadata=row["metadata"],
                )
            )

        if not review_records:
            return 0

        self._db.add_all(review_records)
        self._db.flush()
        return len(review_records)

    def find_cached_url_ingestion(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        target_url: str,
    ) -> dict[str, Any] | None:
        cached_run = (
            self._db.query(IngestionRun)
            .filter(
                IngestionRun.workspace_id == workspace_id,
                IngestionRun.product_id == product_id,
                IngestionRun.source_type == IngestionSourceType.SCRAPE.value,
                IngestionRun.status == IngestionRunStatus.SUCCESS.value,
                IngestionRun.outcome_code == IngestionOutcomeCode.OK.value,
                IngestionRun.target_url == target_url,
            )
            .order_by(IngestionRun.completed_at.desc(), IngestionRun.created_at.desc())
            .first()
        )

        if cached_run is None:
            return None

        cached_count = (
            self._db.query(func.count(Review.id))
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
                Review.ingestion_run_id == cached_run.id,
            )
            .scalar()
        )
        cached_reviews = int(cached_count or 0)
        if cached_reviews <= 0:
            total_count = (
                self._db.query(func.count(Review.id))
                .filter(
                    Review.workspace_id == workspace_id,
                    Review.product_id == product_id,
                )
                .scalar()
            )
            cached_reviews = int(total_count or 0)
        if cached_reviews <= 0:
            return None

        cached_diagnostics = cached_run.result_metadata.get("diagnostics", {}) if cached_run.result_metadata else {}
        return {
            "source_ingestion_run_id": cached_run.id,
            "cached_reviews": cached_reviews,
            "source_diagnostics": cached_diagnostics if isinstance(cached_diagnostics, dict) else {},
        }


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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


def _platform_from_host(source_host: str | None) -> str:
    host = _safe_text(source_host)
    if not host:
        return "unknown"

    parsed = host
    if "://" in host:
        parsed = urlparse(host).netloc or host

    labels = [label for label in parsed.split(".") if label and label not in {"www", "m"}]
    if not labels:
        return "unknown"
    return labels[0].lower()


def _review_fingerprint(
    *,
    platform: str,
    body: str,
    author: str | None,
    reviewed_at: date | None,
    rating: Decimal | None,
) -> str:
    normalized = "|".join(
        [
            platform,
            body.strip().lower(),
            (author or "").strip().lower(),
            reviewed_at.isoformat() if reviewed_at else "",
            str(rating) if rating is not None else "",
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
