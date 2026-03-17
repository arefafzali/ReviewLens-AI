"""Standardized API error response models."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Core error details returned in API error responses."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: dict[str, Any] | None = Field(
        default=None,
        description="Optional structured details for debugging and clients.",
    )


class APIErrorResponse(BaseModel):
    """Base error response envelope used by all API endpoints."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
