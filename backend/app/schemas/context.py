"""Typed contracts for workspace/product context bootstrap APIs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EnsureContextRequest(BaseModel):
    """Request payload to ensure workspace and product references exist."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    product_id: UUID
    platform: str = Field(default="unknown", min_length=1, max_length=50)
    product_name: str | None = Field(default=None, max_length=255)
    source_url: HttpUrl | None = None


class EnsureContextResponse(BaseModel):
    """Response describing ensured context resources."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    product_id: UUID
    created_workspace: bool
    created_product: bool
