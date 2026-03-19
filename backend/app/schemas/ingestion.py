"""Typed contracts for ingestion orchestration APIs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class IngestionSourceType(str, Enum):
    SCRAPE = "scrape"
    CSV_UPLOAD = "csv_upload"


class IngestionRunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class IngestionOutcomeCode(str, Enum):
    OK = "ok"
    LOW_DATA = "low_data"
    BLOCKED = "blocked"
    PARSE_FAILED = "parse_failed"
    UNSUPPORTED_SOURCE = "unsupported_source"
    INVALID_URL = "invalid_url"
    EMPTY_CSV = "empty_csv"
    MALFORMED_CSV = "malformed_csv"


class URLIngestionRequest(BaseModel):
    """Input contract for a URL ingestion attempt."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    product_id: UUID
    target_url: HttpUrl
    reload: bool = Field(
        default=False,
        description="If true, bypass cache and force fresh extraction from source.",
    )

    @field_validator("target_url")
    @classmethod
    def validate_supported_platform_url(cls, value: HttpUrl) -> HttpUrl:
        from app.services.ingestion.url_safety import validate_public_fetch_url

        validate_public_fetch_url(str(value))
        return value


class CSVIngestionRequest(BaseModel):
    """Input contract for a CSV ingestion attempt."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    product_id: UUID
    source_ref: str = Field(min_length=1, max_length=2048)
    csv_content: str = Field(default="")


class IngestionAttemptResponse(BaseModel):
    """Structured result contract returned by ingestion attempt endpoints."""

    model_config = ConfigDict(extra="forbid")

    ingestion_run_id: UUID
    source_type: IngestionSourceType
    status: IngestionRunStatus
    outcome_code: IngestionOutcomeCode
    captured_reviews: int = Field(ge=0)
    message: str
    warnings: list[str] = Field(default_factory=list)
    diagnostics: dict[str, object] = Field(default_factory=dict)
    summary_snapshot: dict[str, object] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
