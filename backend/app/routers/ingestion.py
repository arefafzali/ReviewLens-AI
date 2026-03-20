"""Route-level ingestion orchestration APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db_session
from app.repositories.ingestion_runs import IngestionRunRepository
from app.schemas.ingestion import CSVIngestionRequest, IngestionAttemptResponse, URLIngestionRequest
from app.services.ingestion_service import IngestionOrchestrationService
from app.services.workspace_context import resolve_workspace_id

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
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> IngestionAttemptResponse:
    settings = get_settings()
    workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=payload.workspace_id,
    )

    scoped_payload = payload.model_copy(update={"workspace_id": workspace_id})
    service = IngestionOrchestrationService(IngestionRunRepository(db))
    try:
        return service.attempt_url_ingestion(scoped_payload)
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
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> IngestionAttemptResponse:
    settings = get_settings()
    workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=payload.workspace_id,
    )

    scoped_payload = payload.model_copy(update={"workspace_id": workspace_id})
    service = IngestionOrchestrationService(IngestionRunRepository(db))
    try:
        return service.attempt_csv_ingestion(scoped_payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
