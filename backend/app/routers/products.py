"""Workspace-aware product listing/detail/delete APIs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db_session
from app.schemas.products import ProductDetailResponse, ProductIngestionSnapshot, ProductListItemResponse
from app.services.products_service import ProductsService
from app.services.workspace_context import resolve_workspace_id

router = APIRouter(prefix="/products")


@router.get(
    "",
    response_model=list[ProductListItemResponse],
    summary="List products for a workspace",
    description="Returns workspace-scoped products with summary metrics for dashboard/listing pages.",
)
def list_products(
    request: Request,
    response: Response,
    workspace_id: UUID | None = None,
    db: Session = Depends(get_db_session),
) -> list[ProductListItemResponse]:
    settings = get_settings()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=workspace_id,
    )

    service = ProductsService(db)
    projections = service.list_products(workspace_id=resolved_workspace_id)
    return [
        ProductListItemResponse(
            id=item.product.id,
            workspace_id=item.product.workspace_id,
            platform=item.product.platform,
            name=item.product.name,
            source_url=item.product.source_url,
            total_reviews=item.total_reviews,
            average_rating=item.average_rating,
            chat_session_count=item.chat_session_count,
            latest_ingestion=ProductIngestionSnapshot(
                ingestion_run_id=item.latest_ingestion_run_id,
                status=item.latest_ingestion_status,
                outcome_code=item.latest_ingestion_outcome_code,
                completed_at=item.latest_ingestion_completed_at,
            ),
            updated_at=item.product.updated_at,
        )
        for item in projections
    ]


@router.get(
    "/{product_id}",
    response_model=ProductDetailResponse,
    summary="Get one product",
    description="Returns detailed product metrics and latest ingestion snapshot for detail pages.",
)
def get_product(
    product_id: UUID,
    request: Request,
    response: Response,
    workspace_id: UUID | None = None,
    db: Session = Depends(get_db_session),
) -> ProductDetailResponse:
    settings = get_settings()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=workspace_id,
    )

    service = ProductsService(db)
    projection = service.get_product(workspace_id=resolved_workspace_id, product_id=product_id)
    if projection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for workspace.")

    product = projection.product
    return ProductDetailResponse(
        id=product.id,
        workspace_id=product.workspace_id,
        platform=product.platform,
        external_product_id=product.external_product_id,
        name=product.name,
        source_url=product.source_url,
        stats=dict(product.stats or {}),
        total_reviews=projection.total_reviews,
        average_rating=projection.average_rating,
        chat_session_count=projection.chat_session_count,
        latest_ingestion=ProductIngestionSnapshot(
            ingestion_run_id=projection.latest_ingestion_run_id,
            status=projection.latest_ingestion_status,
            outcome_code=projection.latest_ingestion_outcome_code,
            completed_at=projection.latest_ingestion_completed_at,
        ),
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete one product",
    description="Deletes a workspace-scoped product and dependent ingestion/review/chat data.",
)
def delete_product(
    product_id: UUID,
    request: Request,
    response: Response,
    workspace_id: UUID | None = None,
    db: Session = Depends(get_db_session),
) -> Response:
    settings = get_settings()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=workspace_id,
    )

    service = ProductsService(db)
    deleted = service.delete_product(workspace_id=resolved_workspace_id, product_id=product_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found for workspace.")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
