"""SSE chat endpoint for guardrailed Q&A flow."""

from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db_session
from app.llm.factory import build_llm_provider
from app.schemas.chat import ChatHistoryResponse, ChatStreamRequest, PersistedChatMessage
from app.services.chat.chat_stream_service import (
    ChatStreamService,
    classify_response,
    format_sse_event,
)
from app.services.chat.conversation_memory import ConversationMemoryService
from app.services.workspace_context import resolve_workspace_id

router = APIRouter(prefix="/chat")


@router.get(
    "/history",
    response_model=ChatHistoryResponse,
    summary="Load recent persisted chat history",
    description="Returns a bounded recent conversation window for a given workspace/product and optional session id.",
)
def get_chat_history(
    request: Request,
    response: Response,
    product_id: UUID,
    workspace_id: UUID | None = None,
    chat_session_id: UUID | None = None,
    max_turns: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db_session),
) -> ChatHistoryResponse:
    settings = get_settings()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=workspace_id,
    )

    memory = ConversationMemoryService(db)
    history = memory.get_recent_history(
        workspace_id=resolved_workspace_id,
        product_id=product_id,
        session_id=chat_session_id,
        max_turns=max_turns,
    )
    if history is None:
        raise HTTPException(status_code=404, detail="No chat history found for this workspace/product context.")

    return ChatHistoryResponse(
        chat_session_id=history.session_id,
        messages=[
            PersistedChatMessage(
                message_index=item.message_index,
                role=item.role,
                content=item.content,
                is_refusal=item.is_refusal,
                metadata=item.metadata,
            )
            for item in history.messages
        ],
    )


@router.post(
    "/stream",
    summary="Stream guardrailed chat response over SSE",
    description="Loads bounded conversation context, retrieves review evidence, builds a scoped prompt, and streams response tokens.",
)
def stream_chat(
    payload: ChatStreamRequest,
    request: Request,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    settings = get_settings()
    cookie_response = Response()
    resolved_workspace_id = resolve_workspace_id(
        db=db,
        response=cookie_response,
        settings=settings,
        cookie_workspace_raw=request.cookies.get(settings.workspace_cookie_name),
        requested_workspace_id=payload.workspace_id,
    )

    scoped_payload = payload.model_copy(update={"workspace_id": resolved_workspace_id})

    provider = build_llm_provider(settings)
    if provider is None:
        raise HTTPException(status_code=500, detail="Configured LLM provider is unavailable.")

    service = ChatStreamService(db, provider)

    try:
        context = service.prepare_context(
            workspace_id=scoped_payload.workspace_id,
            product_id=scoped_payload.product_id,
            question=scoped_payload.question,
            session_id=scoped_payload.chat_session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    def event_stream() -> Generator[str, None, None]:
        final_parts: list[str] = []
        try:
            yield format_sse_event(
                "meta",
                {
                    "chat_session_id": str(context.session_id),
                    "provider": provider.provider_name,
                    "history_message_count": len(context.prompt_messages) - 2,
                },
            )

            yield format_sse_event("citations", {"items": context.citations})

            token_parts = service.stream_answer(
                messages=context.prompt_messages,
                citations=context.citations,
                question=scoped_payload.question,
            )
            for token in token_parts:
                final_parts.append(token)
                yield format_sse_event("token", {"text": token})

            final_text = "".join(final_parts).strip()
            classification = classify_response(final_text)

            service.persist_turn(
                workspace_id=scoped_payload.workspace_id,
                product_id=scoped_payload.product_id,
                session_id=context.session_id,
                question=scoped_payload.question,
                answer=final_text,
                classification=classification,
                citations=context.citations,
            )
            db.commit()

            yield format_sse_event(
                "done",
                {
                    "classification": classification.value,
                    "chat_session_id": str(context.session_id),
                    "citations": context.citations,
                    "answer": final_text,
                },
            )
        except Exception as exc:
            db.rollback()
            yield format_sse_event("error", {"code": "CHAT_STREAM_ERROR", "message": str(exc)})

    stream_response = StreamingResponse(event_stream(), media_type="text/event-stream")
    set_cookie_header = cookie_response.headers.get("set-cookie")
    if set_cookie_header:
        stream_response.headers.append("set-cookie", set_cookie_header)
    return stream_response
