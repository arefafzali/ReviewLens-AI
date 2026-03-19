"""ORM models required by ingestion orchestration."""

from __future__ import annotations

from datetime import date
from datetime import datetime, timezone
import uuid

from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), default="capterra", nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    outcome_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    csv_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    records_ingested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    summary_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    ingestion_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="SET NULL"), nullable=True
    )
    source_platform: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    source_review_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    review_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    chat_session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    message_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_refusal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    message_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
