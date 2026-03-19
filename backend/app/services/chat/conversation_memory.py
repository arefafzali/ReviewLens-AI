"""Bounded conversation-memory service for guardrailed chat requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.llm.base import LLMMessage
from app.repositories.chat_memory import ChatMemoryRepository


@dataclass(frozen=True)
class ConversationMemoryContext:
    """Conversation context payload passed to chat orchestration."""

    session_id: UUID
    recent_messages: list[LLMMessage]


@dataclass(frozen=True)
class PersistedConversationMessage:
    """Persisted message contract used by history-hydration APIs."""

    message_index: int
    role: str
    content: str
    is_refusal: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class PersistedConversationHistory:
    """Resolved chat history payload for an existing or latest session."""

    session_id: UUID
    messages: list[PersistedConversationMessage]


class ConversationMemoryService:
    """Handles chat session lifecycle and bounded recent-history retrieval."""

    DEFAULT_MAX_TURNS = 6

    def __init__(self, db: Session) -> None:
        self._repository = ChatMemoryRepository(db)

    def get_or_create_context(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        session_id: UUID | None = None,
        title: str | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> ConversationMemoryContext:
        session = self._repository.get_or_create_session(
            workspace_id=workspace_id,
            product_id=product_id,
            session_id=session_id,
            title=title,
        )
        window = self._repository.load_recent_window(
            session_id=session.id,
            workspace_id=workspace_id,
            product_id=product_id,
            max_turns=max_turns,
        )
        recent = [LLMMessage(role=item.role, content=item.content) for item in window]
        return ConversationMemoryContext(session_id=session.id, recent_messages=recent)

    def save_turn(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        session_id: UUID,
        user_message: str,
        assistant_message: str,
        assistant_is_refusal: bool = False,
        assistant_metadata: dict[str, Any] | None = None,
    ) -> None:
        session = self._repository.get_or_create_session(
            workspace_id=workspace_id,
            product_id=product_id,
            session_id=session_id,
        )
        self._repository.append_turn(
            session=session,
            user_message=user_message,
            assistant_message=assistant_message,
            assistant_is_refusal=assistant_is_refusal,
            assistant_metadata=assistant_metadata,
        )

    def get_recent_history(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        session_id: UUID | None = None,
        max_turns: int = DEFAULT_MAX_TURNS,
    ) -> PersistedConversationHistory | None:
        if session_id is not None:
            session = self._repository.get_session(
                workspace_id=workspace_id,
                product_id=product_id,
                session_id=session_id,
            )
        else:
            session = self._repository.get_latest_session(
                workspace_id=workspace_id,
                product_id=product_id,
            )

        if session is None:
            return None

        window = self._repository.load_recent_window(
            session_id=session.id,
            workspace_id=workspace_id,
            product_id=product_id,
            max_turns=max_turns,
        )
        persisted = [
            PersistedConversationMessage(
                message_index=item.message_index,
                role=item.role,
                content=item.content,
                is_refusal=item.is_refusal,
                metadata=dict(item.message_metadata or {}),
            )
            for item in window
        ]
        return PersistedConversationHistory(session_id=session.id, messages=persisted)
