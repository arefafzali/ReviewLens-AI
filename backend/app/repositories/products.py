"""Persistence repository for workspace-scoped product APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession, IngestionRun, Product, Review


@dataclass(frozen=True)
class ProductProjection:
    """Product API projection with summary metrics."""

    product: Product
    total_reviews: int
    average_rating: float | None
    chat_session_count: int
    latest_ingestion_run_id: UUID | None
    latest_ingestion_status: str | None
    latest_ingestion_outcome_code: str | None
    latest_ingestion_completed_at: datetime | None


class ProductRepository:
    """Encapsulates workspace-aware product list/detail/delete operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_products(self, *, workspace_id: UUID) -> list[ProductProjection]:
        rows = (
            self._db.query(Product)
            .filter(Product.workspace_id == workspace_id)
            .order_by(Product.updated_at.desc(), Product.created_at.desc())
            .all()
        )
        return [self._build_projection(product=item) for item in rows]

    def get_product(self, *, workspace_id: UUID, product_id: UUID) -> ProductProjection | None:
        product = (
            self._db.query(Product)
            .filter(
                Product.workspace_id == workspace_id,
                Product.id == product_id,
            )
            .first()
        )
        if product is None:
            return None
        return self._build_projection(product=product)

    def delete_product(self, *, workspace_id: UUID, product_id: UUID) -> bool:
        product = (
            self._db.query(Product)
            .filter(
                Product.workspace_id == workspace_id,
                Product.id == product_id,
            )
            .first()
        )
        if product is None:
            return False

        (
            self._db.query(ChatMessage)
            .filter(
                ChatMessage.workspace_id == workspace_id,
                ChatMessage.product_id == product_id,
            )
            .delete(synchronize_session=False)
        )
        (
            self._db.query(ChatSession)
            .filter(
                ChatSession.workspace_id == workspace_id,
                ChatSession.product_id == product_id,
            )
            .delete(synchronize_session=False)
        )
        (
            self._db.query(Review)
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
            )
            .delete(synchronize_session=False)
        )
        (
            self._db.query(IngestionRun)
            .filter(
                IngestionRun.workspace_id == workspace_id,
                IngestionRun.product_id == product_id,
            )
            .delete(synchronize_session=False)
        )
        self._db.delete(product)
        self._db.flush()
        return True

    def _build_projection(self, *, product: Product) -> ProductProjection:
        review_count = (
            self._db.query(func.count(Review.id))
            .filter(
                Review.workspace_id == product.workspace_id,
                Review.product_id == product.id,
            )
            .scalar()
        )
        chat_session_count = (
            self._db.query(func.count(ChatSession.id))
            .filter(
                ChatSession.workspace_id == product.workspace_id,
                ChatSession.product_id == product.id,
            )
            .scalar()
        )
        latest_ingestion = (
            self._db.query(IngestionRun)
            .filter(
                IngestionRun.workspace_id == product.workspace_id,
                IngestionRun.product_id == product.id,
            )
            .order_by(IngestionRun.completed_at.desc(), IngestionRun.created_at.desc())
            .first()
        )

        stats = product.stats if isinstance(product.stats, dict) else {}
        average_rating = _safe_float(stats.get("average_rating"))
        return ProductProjection(
            product=product,
            total_reviews=int(review_count or 0),
            average_rating=average_rating,
            chat_session_count=int(chat_session_count or 0),
            latest_ingestion_run_id=latest_ingestion.id if latest_ingestion is not None else None,
            latest_ingestion_status=latest_ingestion.status if latest_ingestion is not None else None,
            latest_ingestion_outcome_code=latest_ingestion.outcome_code if latest_ingestion is not None else None,
            latest_ingestion_completed_at=latest_ingestion.completed_at if latest_ingestion is not None else None,
        )


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    return None
