"""Workspace-aware product service for list/detail/delete APIs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.repositories.products import ProductProjection, ProductRepository


class ProductsService:
    """Coordinates product repository operations and transaction boundaries."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repository = ProductRepository(db)

    def list_products(self, *, workspace_id: UUID) -> list[ProductProjection]:
        return self._repository.list_products(workspace_id=workspace_id)

    def get_product(self, *, workspace_id: UUID, product_id: UUID) -> ProductProjection | None:
        return self._repository.get_product(workspace_id=workspace_id, product_id=product_id)

    def delete_product(self, *, workspace_id: UUID, product_id: UUID) -> bool:
        deleted = self._repository.delete_product(workspace_id=workspace_id, product_id=product_id)
        if not deleted:
            self._db.rollback()
            return False
        self._db.commit()
        return True
