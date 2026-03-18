"""Route-level ingestion orchestration APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import CSVIngestionRequest, IngestionAttemptResponse, URLIngestionRequest
from app.services.ingestion_service import IngestionOrchestrationService

router = APIRouter(prefix="/ingestion")


@router.post(
    "/url",
    response_model=IngestionAttemptResponse,
    summary="Run URL ingestion orchestration",
    description=(
        "Creates and finalizes an ingestion run for a public review URL. "
        "Fetching is provider-backed and parsing uses a host-agnostic generic extractor."
    ),
)
def ingest_from_url(
    payload: URLIngestionRequest,
    db: Session = Depends(get_db_session),
) -> IngestionAttemptResponse:
    service = IngestionOrchestrationService(IngestionRunRepository(db))
    try:
        return service.attempt_url_ingestion(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/csv",
    response_model=IngestionAttemptResponse,
    summary="Run CSV ingestion orchestration",
    description="Creates and finalizes an ingestion run for a CSV ingestion attempt.",
)
def ingest_from_csv(
    payload: CSVIngestionRequest,
    db: Session = Depends(get_db_session),
) -> IngestionAttemptResponse:
    service = IngestionOrchestrationService(IngestionRunRepository(db))
    try:
        return service.attempt_csv_ingestion(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
