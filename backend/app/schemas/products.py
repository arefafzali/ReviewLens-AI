"""Typed contracts for workspace-aware product listing/detail APIs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductIngestionSnapshot(BaseModel):
    """Latest ingestion status summary for a product."""

    model_config = ConfigDict(extra="forbid")

    ingestion_run_id: UUID | None = None
    status: str | None = None
    outcome_code: str | None = None
    completed_at: datetime | None = None


class ProductListItemResponse(BaseModel):
    """Compact product card payload used by dashboard/listing pages."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace_id: UUID
    platform: str
    name: str
    source_url: str
    total_reviews: int = Field(ge=0)
    average_rating: float | None = None
    chat_session_count: int = Field(ge=0)
    latest_ingestion: ProductIngestionSnapshot
    updated_at: datetime


class ProductDetailResponse(BaseModel):
    """Detailed product payload used by product detail pages."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    workspace_id: UUID
    platform: str
    external_product_id: str | None = None
    name: str
    source_url: str
    stats: dict[str, object] = Field(default_factory=dict)
    total_reviews: int = Field(ge=0)
    average_rating: float | None = None
    chat_session_count: int = Field(ge=0)
    latest_ingestion: ProductIngestionSnapshot
    created_at: datetime
    updated_at: datetime
