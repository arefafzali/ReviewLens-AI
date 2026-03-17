"""Health check endpoints for liveness and readiness."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Simple health status payload."""

    model_config = ConfigDict(extra="forbid")

    status: str


router = APIRouter(prefix="/health")


@router.get(
    "/live",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns a liveness signal indicating the API process is running.",
)
def liveness() -> HealthResponse:
    """Return service liveness status."""

    return HealthResponse(status="live")


@router.get(
    "/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Returns a readiness signal indicating the API can accept requests.",
)
def readiness() -> HealthResponse:
    """Return service readiness status."""

    return HealthResponse(status="ready")
