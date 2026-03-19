"""Persistence repository for bounded chat session memory."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import ChatMessage, ChatSession


@dataclass(frozen=True)
class ChatWindowMessage:
    """Projected chat message shape for prompt-context assembly."""

    message_index: int
    role: str
    content: str
    is_refusal: bool
    created_at: datetime


class ChatMemoryRepository:
    """Encapsulates chat-session lookup, message persistence, and bounded history."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create_session(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        session_id: UUID | None = None,
        title: str | None = None,
    ) -> ChatSession:
        if session_id is not None:
            existing = (
                self._db.query(ChatSession)
                .filter(
                    ChatSession.id == session_id,
                    ChatSession.workspace_id == workspace_id,
                    ChatSession.product_id == product_id,
                )
                .first()
            )
            if existing is not None:
                return existing

        now = datetime.now(timezone.utc)
        created = ChatSession(
            id=session_id,
            workspace_id=workspace_id,
            product_id=product_id,
            title=_safe_title(title),
            started_at=now,
            last_activity_at=now,
            created_at=now,
            updated_at=now,
        )
        self._db.add(created)
        self._db.flush()
        return created

    def append_message(
        self,
        *,
        session: ChatSession,
        role: str,
        content: str,
        is_refusal: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> ChatMessage:
        now = datetime.now(timezone.utc)
        next_index = self._next_message_index(chat_session_id=session.id)
        message = ChatMessage(
            chat_session_id=session.id,
            workspace_id=session.workspace_id,
            product_id=session.product_id,
            message_index=next_index,
            role=role,
            content=content,
            is_refusal=is_refusal,
            message_metadata=dict(metadata or {}),
            created_at=now,
        )
        session.last_activity_at = now
        session.updated_at = now

        self._db.add(message)
        self._db.add(session)
        self._db.flush()
        return message

    def append_turn(
        self,
        *,
        session: ChatSession,
        user_message: str,
        assistant_message: str,
        assistant_is_refusal: bool = False,
        assistant_metadata: dict[str, Any] | None = None,
    ) -> tuple[ChatMessage, ChatMessage]:
        user_saved = self.append_message(
            session=session,
            role="user",
            content=user_message,
            is_refusal=False,
        )
        assistant_saved = self.append_message(
            session=session,
            role="assistant",
            content=assistant_message,
            is_refusal=assistant_is_refusal,
            metadata=assistant_metadata,
        )
        return user_saved, assistant_saved

    def load_recent_window(
        self,
        *,
        session_id: UUID,
        workspace_id: UUID,
        product_id: UUID,
        max_turns: int = 6,
    ) -> list[ChatWindowMessage]:
        max_messages = max(1, max_turns) * 2

        rows = (
            self._db.query(ChatMessage)
            .filter(
                ChatMessage.chat_session_id == session_id,
                ChatMessage.workspace_id == workspace_id,
                ChatMessage.product_id == product_id,
            )
            .order_by(ChatMessage.message_index.desc())
            .limit(max_messages)
            .all()
        )

        rows.reverse()
        return [
            ChatWindowMessage(
                message_index=item.message_index,
                role=item.role,
                content=item.content,
                is_refusal=bool(item.is_refusal),
                created_at=item.created_at,
            )
            for item in rows
        ]

    def _next_message_index(self, *, chat_session_id: UUID) -> int:
        current_max = (
            self._db.query(func.max(ChatMessage.message_index))
            .filter(ChatMessage.chat_session_id == chat_session_id)
            .scalar()
        )
        return int(current_max or 0) + 1


def _safe_title(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned[:255] if cleaned else None
