"""API tests for SSE chat streaming with structured classification and citations."""

from __future__ import annotations

import json
import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, Product, Review, Workspace
from app.db.session import get_db_session
from app.llm.fake_provider import FakeLLMProvider
from app.config import get_settings


def _build_app_with_db() -> tuple[TestClient, Session, object]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import create_app

    app = create_app()

    def override_db_session():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app), Session(engine), app


def _seed_context(db: Session, *, with_review: bool = True) -> tuple[str, str]:
    workspace_id = uuid.uuid4()
    product_id = uuid.uuid4()

    db.add(Workspace(id=workspace_id, name="Chat Workspace"))
    db.add(
        Product(
            id=product_id,
            workspace_id=workspace_id,
            platform="generic_source",
            name="PressPage",
            source_url="https://www.reviews.example.com/p/164876/PressPage/reviews/",
            stats={"total_reviews": 1, "average_rating": 4.8},
        )
    )

    if with_review:
        db.add(
            Review(
                workspace_id=workspace_id,
                product_id=product_id,
                source_platform="generic_source",
                review_fingerprint="r1",
                title="Fast onboarding",
                body="Onboarding was fast and support was helpful.",
                rating=4.8,
                author_name="Ari",
            )
        )

    db.commit()
    return str(workspace_id), str(product_id)


def _parse_sse_lines(lines: list[str | bytes]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    current_event: str | None = None
    current_data: str | None = None

    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        line = line.strip("\r")
        if line.startswith("event:"):
            if current_event is not None and current_data is not None:
                events.append({"event": current_event, "data": json.loads(current_data)})
            current_event = line.split(":", 1)[1].strip()
            current_data = None
        elif line.startswith("data:"):
            current_data = line.split(":", 1)[1].strip()

    if current_event is not None and current_data is not None:
        events.append({"event": current_event, "data": json.loads(current_data)})

    return events


def _post_stream_events(client: TestClient, payload: dict[str, object]) -> tuple[int, str, list[dict[str, object]]]:
    response = client.post("/chat/stream", json=payload)
    body = response.text
    lines = body.splitlines()
    content_type = response.headers.get("content-type", "")
    status_code = response.status_code
    events = _parse_sse_lines(lines)

    if not events and "event:" in body and "data:" in body:
        compact_matches = re.findall(r"event:\s*([a-z_]+)\s*data:\s*(\{.*?\})(?=\s*event:|\s*$)", body, flags=re.IGNORECASE)
        for event_name, raw_json in compact_matches:
            events.append({"event": event_name, "data": json.loads(raw_json)})

    return status_code, content_type, events


def test_chat_stream_sends_tokens_citations_and_answer_classification(monkeypatch) -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(chat_response="The reviews highlight fast onboarding and responsive support."),
    )

    first_status, first_content_type, events_first = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "question": "What do users say about onboarding?",
        },
    )
    assert first_status == 200
    assert first_content_type.startswith("text/event-stream")

    event_names_first = [item["event"] for item in events_first]
    assert "meta" in event_names_first
    assert "citations" in event_names_first
    assert "token" in event_names_first
    assert "done" in event_names_first

    meta = next(item for item in events_first if item["event"] == "meta")
    citations = next(item for item in events_first if item["event"] == "citations")
    done = next(item for item in events_first if item["event"] == "done")

    assert meta["data"]["history_message_count"] == 0
    assert len(citations["data"]["items"]) >= 1
    assert done["data"]["classification"] == "answer"

    session_id = done["data"]["chat_session_id"]

    second_status, _, events_second = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "chat_session_id": session_id,
            "question": "And what concerns are mentioned?",
        },
    )
    assert second_status == 200
    meta_second = next(item for item in events_second if item["event"] == "meta")
    assert meta_second["data"]["history_message_count"] == 2

    stored = verify_db.query(ChatMessage).all()
    assert len(stored) == 4

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_stream_classifies_out_of_scope_refusal(monkeypatch) -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(
            chat_response=(
                "REFUSAL: I can only answer from the ingested reviews for the selected product/platform. "
                "REASON: The question asks about competitor benchmarks. "
                "NEXT_STEP: Ask about themes present in PressPage reviews."
            )
        ),
    )

    status_code, _, events = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "question": "How does this compare with G2 competitors?",
        },
    )

    assert status_code == 200
    done = next(item for item in events if item["event"] == "done")

    assert done["data"]["classification"] == "out_of_scope"

    latest = verify_db.query(ChatMessage).order_by(ChatMessage.message_index.desc()).first()
    assert latest is not None
    assert latest.role == "assistant"
    assert latest.is_refusal is True

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_stream_classifies_insufficient_evidence(monkeypatch) -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=False)

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(
            chat_response=(
                "INSUFFICIENT_EVIDENCE: The ingested reviews provided do not contain enough evidence to answer confidently. "
                "WHAT_IS_MISSING: Feedback about enterprise security workflows. "
                "NEXT_STEP: Add more reviews from the same product/platform."
            )
        ),
    )

    status_code, _, events = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "question": "What do reviews say about enterprise security controls?",
        },
    )

    assert status_code == 200
    done = next(item for item in events if item["event"] == "done")
    citations = next(item for item in events if item["event"] == "citations")

    assert done["data"]["classification"] == "insufficient_evidence"
    assert citations["data"]["items"] == []

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_history_returns_recent_messages_for_latest_session(monkeypatch) -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(chat_response="The reviews highlight fast onboarding and responsive support."),
    )

    status_code, _, events = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "question": "What do users say about onboarding?",
        },
    )
    assert status_code == 200
    done = next(item for item in events if item["event"] == "done")
    session_id = done["data"]["chat_session_id"]

    second_status, _, _ = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "chat_session_id": session_id,
            "question": "What concerns are mentioned?",
        },
    )
    assert second_status == 200

    history = client.get(
        "/chat/history",
        params={
            "workspace_id": workspace_id,
            "product_id": product_id,
        },
    )
    assert history.status_code == 200
    payload = history.json()
    assert payload["chat_session_id"] == session_id
    assert len(payload["messages"]) == 4
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "assistant"
    assert isinstance(payload["messages"][1]["metadata"], dict)

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_history_respects_max_turns(monkeypatch) -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    monkeypatch.setattr(
        "app.routers.chat.build_llm_provider",
        lambda *_: FakeLLMProvider(chat_response="Grounded answer."),
    )

    first_status, _, first_events = _post_stream_events(
        client,
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "question": "Q1",
        },
    )
    assert first_status == 200
    session_id = next(item for item in first_events if item["event"] == "done")["data"]["chat_session_id"]

    for question in ["Q2", "Q3"]:
        follow_status, _, _ = _post_stream_events(
            client,
            {
                "workspace_id": workspace_id,
                "product_id": product_id,
                "chat_session_id": session_id,
                "question": question,
            },
        )
        assert follow_status == 200

    history = client.get(
        "/chat/history",
        params={
            "workspace_id": workspace_id,
            "product_id": product_id,
            "chat_session_id": session_id,
            "max_turns": 2,
        },
    )
    assert history.status_code == 200
    payload = history.json()
    assert payload["chat_session_id"] == session_id
    assert len(payload["messages"]) == 4
    assert payload["messages"][0]["content"] == "Q2"
    assert payload["messages"][2]["content"] == "Q3"

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_history_returns_not_found_when_no_session_exists() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    history = client.get(
        "/chat/history",
        params={
            "workspace_id": workspace_id,
            "product_id": product_id,
        },
    )
    assert history.status_code == 404

    app.dependency_overrides.clear()
    verify_db.close()


def test_chat_history_resolves_workspace_from_cookie() -> None:
    client, verify_db, app = _build_app_with_db()
    workspace_id, product_id = _seed_context(verify_db, with_review=True)

    from app.db.models import ChatSession

    session_id = uuid.uuid4()
    verify_db.add(
        ChatSession(
            id=session_id,
            workspace_id=uuid.UUID(workspace_id),
            product_id=uuid.UUID(product_id),
            title="History Session",
        )
    )
    verify_db.add(
        ChatMessage(
            chat_session_id=session_id,
            workspace_id=uuid.UUID(workspace_id),
            product_id=uuid.UUID(product_id),
            message_index=1,
            role="user",
            content="What do users say?",
        )
    )
    verify_db.add(
        ChatMessage(
            chat_session_id=session_id,
            workspace_id=uuid.UUID(workspace_id),
            product_id=uuid.UUID(product_id),
            message_index=2,
            role="assistant",
            content="Users mention fast onboarding.",
        )
    )
    verify_db.commit()

    client.cookies.set(get_settings().workspace_cookie_name, workspace_id)
    history = client.get(
        "/chat/history",
        params={
            "product_id": product_id,
        },
    )

    assert history.status_code == 200
    payload = history.json()
    assert payload["chat_session_id"] == str(session_id)
    assert len(payload["messages"]) == 2

    app.dependency_overrides.clear()
    verify_db.close()

