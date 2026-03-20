"""Workspace/product context bootstrap APIs."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Product, Workspace
from app.db.session import get_db_session
from app.schemas.context import EnsureContextRequest, EnsureContextResponse
from app.services.workspace_context import resolve_workspace_id

router = APIRouter(prefix="/context")


@router.post(
    "/ensure",
    response_model=EnsureContextResponse,
    summary="Ensure workspace and product context",
    description="Creates missing workspace/product records for the provided IDs and returns idempotent context state.",
)
def ensure_context(
    payload: EnsureContextRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db_session),
) -> EnsureContextResponse:
    settings = get_settings()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=payload.workspace_id,
    )

    scoped_payload = payload.model_copy(update={"workspace_id": resolved_workspace_id})

    now = datetime.now(timezone.utc)

    workspace = db.query(Workspace).filter(Workspace.id == scoped_payload.workspace_id).first()
    created_workspace = False
    if workspace is None:
        workspace = Workspace(
            id=scoped_payload.workspace_id,
            name="Anonymous Workspace",
            created_at=now,
            updated_at=now,
        )
        db.add(workspace)
        db.flush()
        created_workspace = True

    product = (
        db.query(Product)
        .filter(
            Product.id == scoped_payload.product_id,
            Product.workspace_id == scoped_payload.workspace_id,
        )
        .first()
    )
    created_product = False
    if product is None:
        conflicting_product = db.query(Product).filter(Product.id == payload.product_id).first()
        if conflicting_product is not None and conflicting_product.workspace_id != scoped_payload.workspace_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="product_id already exists under a different workspace",
            )

        product = Product(
            id=scoped_payload.product_id,
            workspace_id=scoped_payload.workspace_id,
            platform=scoped_payload.platform.strip().lower(),
            name=scoped_payload.product_name or "Analyst Product",
            source_url=(
                str(scoped_payload.source_url)
                if scoped_payload.source_url is not None
                else "https://example.com/reviews"
            ),
            created_at=now,
            updated_at=now,
        )
        db.add(product)
        created_product = True

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to ensure workspace/product context due to conflicting IDs.",
        ) from exc

    return EnsureContextResponse(
        workspace_id=scoped_payload.workspace_id,
        product_id=scoped_payload.product_id,
        created_workspace=created_workspace,
        created_product=created_product,
    )
