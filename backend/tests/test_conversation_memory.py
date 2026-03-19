"""Tests for bounded backend conversation memory behavior."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import ChatMessage, Product, Workspace
from app.services.chat.conversation_memory import ConversationMemoryService


def _setup_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_context(db: Session) -> tuple[uuid.UUID, uuid.UUID]:
    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()

    db.add(Workspace(id=workspace_id, name="Memory Workspace"))
    db.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="capterra",
            name="Memory Product",
            source_url="https://www.capterra.com/p/164876/PressPage/reviews/",
        )
    )
    db.commit()
    return workspace_id, product_id


def test_context_creation_and_lookup_by_session_id() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_context(db)
    service = ConversationMemoryService(db)

    first = service.get_or_create_context(
        workspace_id=workspace_id,
        product_id=product_id,
        title="PressPage analysis",
    )
    second = service.get_or_create_context(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=first.session_id,
    )

    assert first.session_id == second.session_id
    assert second.recent_messages == []


def test_save_turn_persists_user_and_assistant_messages() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_context(db)
    service = ConversationMemoryService(db)

    context = service.get_or_create_context(workspace_id=workspace_id, product_id=product_id)
    service.save_turn(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=context.session_id,
        user_message="What are users saying about onboarding?",
        assistant_message="Users consistently mention faster onboarding with responsive support.",
    )
    db.commit()

    stored = (
        db.query(ChatMessage)
        .filter(ChatMessage.chat_session_id == context.session_id)
        .order_by(ChatMessage.message_index.asc())
        .all()
    )

    assert len(stored) == 2
    assert stored[0].role == "user"
    assert stored[0].message_index == 1
    assert "onboarding" in stored[0].content.lower()
    assert stored[1].role == "assistant"
    assert stored[1].message_index == 2


def test_recent_history_window_is_capped_to_last_six_turns() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_context(db)
    service = ConversationMemoryService(db)

    context = service.get_or_create_context(workspace_id=workspace_id, product_id=product_id)

    for turn in range(1, 9):
        service.save_turn(
            workspace_id=workspace_id,
            product_id=product_id,
            session_id=context.session_id,
            user_message=f"user turn {turn}",
            assistant_message=f"assistant turn {turn}",
        )
    db.commit()

    window = service.get_or_create_context(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=context.session_id,
        max_turns=6,
    )

    assert len(window.recent_messages) == 12
    assert window.recent_messages[0].content == "user turn 3"
    assert window.recent_messages[1].content == "assistant turn 3"
    assert window.recent_messages[-2].content == "user turn 8"
    assert window.recent_messages[-1].content == "assistant turn 8"


def test_followup_question_can_use_recent_window_context() -> None:
    db = _setup_db()
    workspace_id, product_id = _seed_context(db)
    service = ConversationMemoryService(db)

    context = service.get_or_create_context(workspace_id=workspace_id, product_id=product_id)
    service.save_turn(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=context.session_id,
        user_message="Summarize onboarding feedback.",
        assistant_message="Onboarding is praised for speed and clear implementation steps.",
    )
    service.save_turn(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=context.session_id,
        user_message="Which review mentions implementation support?",
        assistant_message="A high-ranked review highlights implementation support responsiveness.",
    )
    db.commit()

    window = service.get_or_create_context(
        workspace_id=workspace_id,
        product_id=product_id,
        session_id=context.session_id,
        max_turns=6,
    )

    transcript = "\n".join(item.content for item in window.recent_messages)
    assert "onboarding" in transcript.lower()
    assert "implementation support" in transcript.lower()
