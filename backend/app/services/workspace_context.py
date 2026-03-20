"""Cookie-based anonymous workspace resolution utilities."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import Response
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Workspace


def _parse_uuid(raw: str | None) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(str(raw))
    except ValueError:
        return None


def ensure_workspace_exists(db: Session, workspace_id: UUID) -> None:
    """Create anonymous workspace row when missing."""

    existing = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if existing is not None:
        return

    now = datetime.now(timezone.utc)
    db.add(
        Workspace(
            id=workspace_id,
            name="Anonymous Workspace",
            created_at=now,
            updated_at=now,
        )
    )
    db.flush()


def resolve_workspace_id(
    *,
    db: Session,
    response: Response,
    settings: Settings,
    cookie_workspace_raw: str | None,
    requested_workspace_id: UUID | None,
) -> UUID:
    """Resolve workspace id from cookie/request and ensure cookie + workspace row exist.

    Resolution order:
    1) Valid cookie workspace id
    2) Explicit workspace id from request payload/query
    3) New generated UUID
    """

    cookie_workspace_id = _parse_uuid(cookie_workspace_raw)

    if cookie_workspace_id is not None:
        resolved = cookie_workspace_id
    elif requested_workspace_id is not None:
        resolved = requested_workspace_id
    else:
        resolved = uuid4()

    ensure_workspace_exists(db, resolved)

    response.set_cookie(
        key=settings.workspace_cookie_name,
        value=str(resolved),
        max_age=settings.workspace_cookie_max_age_seconds,
        secure=settings.workspace_cookie_secure,
        httponly=settings.workspace_cookie_http_only,
        samesite=settings.workspace_cookie_same_site,
        path=settings.workspace_cookie_path,
    )

    return resolved
