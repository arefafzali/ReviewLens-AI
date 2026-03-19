"""Typed contracts for streaming chat APIs."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatClassification(str, Enum):
    ANSWER = "answer"
    OUT_OF_SCOPE = "out_of_scope"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ChatStreamRequest(BaseModel):
    """Input contract for one streaming chat turn."""

    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    product_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    chat_session_id: UUID | None = None


class CitationItem(BaseModel):
    """Machine-readable citation payload for streamed responses."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    review_id: UUID
    title: str | None = None
    snippet: str
    author_name: str | None = None
    reviewed_at: str | None = None
    rating: float | None = None
    rank: float
