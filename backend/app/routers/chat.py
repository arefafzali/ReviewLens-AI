"""SSE chat endpoint for guardrailed Q&A flow."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db_session
from app.llm.factory import build_llm_provider
from app.schemas.chat import ChatStreamRequest
from app.services.chat.chat_stream_service import (
    ChatStreamService,
    classify_response,
    format_sse_event,
)

router = APIRouter(prefix="/chat")


@router.post(
    "/stream",
    summary="Stream guardrailed chat response over SSE",
    description="Loads bounded conversation context, retrieves review evidence, builds a scoped prompt, and streams response tokens.",
)
def stream_chat(
    payload: ChatStreamRequest,
    db: Session = Depends(get_db_session),
) -> StreamingResponse:
    settings = get_settings()
    provider = build_llm_provider(settings)
    if provider is None:
        raise HTTPException(status_code=500, detail="Configured LLM provider is unavailable.")

    service = ChatStreamService(db, provider)

    try:
        context = service.prepare_context(
            workspace_id=payload.workspace_id,
            product_id=payload.product_id,
            question=payload.question,
            session_id=payload.chat_session_id,
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
                question=payload.question,
            )
            for token in token_parts:
                final_parts.append(token)
                yield format_sse_event("token", {"text": token})

            final_text = "".join(final_parts).strip()
            classification = classify_response(final_text)

            service.persist_turn(
                workspace_id=payload.workspace_id,
                product_id=payload.product_id,
                session_id=context.session_id,
                question=payload.question,
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

    return StreamingResponse(event_stream(), media_type="text/event-stream")
