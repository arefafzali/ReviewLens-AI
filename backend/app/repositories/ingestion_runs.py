"""Persistence helpers for ingestion run lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import IngestionRun
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
    ) -> IngestionRun:
        now = datetime.now(timezone.utc)

        run.status = status.value
        run.outcome_code = outcome_code.value
        run.records_ingested = captured_reviews
        run.error_detail = error_detail
        run.result_metadata = {
            "message": message,
            "warnings": warnings or [],
        }
        run.completed_at = now
        run.updated_at = now

        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)
        return run
