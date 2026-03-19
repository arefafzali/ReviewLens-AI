"""Persistence helpers for ingestion run lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import IngestionRun, Product, Review
from app.schemas.ingestion import IngestionOutcomeCode, IngestionRunStatus, IngestionSourceType
from app.services.ingestion.review_analytics import ReviewAnalyticsRow, compute_ingestion_analytics
from app.services.ingestion.review_normalization import normalize_reviews_for_persistence
from app.services.ingestion.review_suggested_questions import (
    DeterministicSuggestedQuestionGenerator,
    SuggestedQuestionGenerator,
)


@dataclass(frozen=True)
class PersistedReviewsResult:
    """Persistence outcome counters for normalized review ingestion."""

    input_reviews: int
    inserted_reviews: int
    duplicates_removed: int
    skipped_missing_body: int


@dataclass(frozen=True)
class IngestionAnalyticsResult:
    """Computed analytics snapshots for product aggregate and ingestion run."""

    product_stats: dict[str, Any]
    summary_snapshot: dict[str, Any]


class IngestionRunRepository:
    """Encapsulates ingestion run create/finalize persistence operations."""

    def __init__(self, db: Session, suggested_question_generator: SuggestedQuestionGenerator | None = None) -> None:
        self._db = db
        self._suggested_question_generator = suggested_question_generator or DeterministicSuggestedQuestionGenerator()

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
        summary_snapshot: dict[str, Any] | None = None,
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
        run.summary_snapshot = summary_snapshot or {}
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
    ) -> PersistedReviewsResult:
        platform = _platform_from_host(source_host)

        normalized = normalize_reviews_for_persistence(platform=platform, reviews=reviews)
        normalized_rows = normalized.normalized_reviews

        if not normalized_rows:
            return PersistedReviewsResult(
                input_reviews=len(reviews),
                inserted_reviews=0,
                duplicates_removed=normalized.duplicates_in_payload,
                skipped_missing_body=normalized.skipped_missing_body,
            )

        incoming_fingerprints = {item.review_fingerprint for item in normalized_rows}
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
        duplicates_existing = 0
        for row in normalized_rows:
            fingerprint = row.review_fingerprint
            if fingerprint in existing_fingerprints:
                duplicates_existing += 1
                continue
            review_records.append(
                Review(
                    workspace_id=workspace_id,
                    product_id=product_id,
                    ingestion_run_id=ingestion_run_id,
                    source_platform=platform,
                    source_review_id=row.source_review_id,
                    review_fingerprint=fingerprint,
                    title=row.title,
                    body=row.body,
                    rating=row.rating,
                    reviewed_at=row.reviewed_at,
                    author_name=row.author_name,
                    language_code=None,
                    review_metadata={"raw": row.raw_payload},
                )
            )

        inserted_count = len(review_records)
        duplicates_removed = normalized.duplicates_in_payload + duplicates_existing

        if not review_records:
            return PersistedReviewsResult(
                input_reviews=len(reviews),
                inserted_reviews=0,
                duplicates_removed=duplicates_removed,
                skipped_missing_body=normalized.skipped_missing_body,
            )

        self._db.add_all(review_records)
        self._db.flush()
        return PersistedReviewsResult(
            input_reviews=len(reviews),
            inserted_reviews=inserted_count,
            duplicates_removed=duplicates_removed,
            skipped_missing_body=normalized.skipped_missing_body,
        )

    def compute_and_store_ingestion_analytics(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        ingestion_run_id: UUID,
    ) -> IngestionAnalyticsResult:
        product_reviews = (
            self._db.query(Review)
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
            )
            .all()
        )
        run_reviews = (
            self._db.query(Review)
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
                Review.ingestion_run_id == ingestion_run_id,
            )
            .all()
        )

        product_rows = [_to_analytics_row(item) for item in product_reviews]
        run_rows = [_to_analytics_row(item) for item in run_reviews]
        product_stats = compute_ingestion_analytics(product_rows)
        summary_snapshot = compute_ingestion_analytics(run_rows)

        product_questions = self._suggested_question_generator.generate_questions(
            analytics=product_stats,
            rows=product_rows,
        )
        summary_questions = self._suggested_question_generator.generate_questions(
            analytics=summary_snapshot,
            rows=run_rows,
        )
        product_stats["suggested_questions"] = product_questions
        summary_snapshot["suggested_questions"] = summary_questions

        product = (
            self._db.query(Product)
            .filter(
                Product.id == product_id,
                Product.workspace_id == workspace_id,
            )
            .first()
        )
        if product is not None:
            product.stats = product_stats
            self._db.add(product)

        return IngestionAnalyticsResult(
            product_stats=product_stats,
            summary_snapshot=summary_snapshot,
        )

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


def _safe_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_analytics_row(review: Review) -> ReviewAnalyticsRow:
    return ReviewAnalyticsRow(
        title=review.title,
        body=review.body,
        rating=review.rating,
        author_name=review.author_name,
        reviewed_at=review.reviewed_at,
        source_review_id=review.source_review_id,
        review_fingerprint=review.review_fingerprint,
        created_at=review.created_at,
    )
