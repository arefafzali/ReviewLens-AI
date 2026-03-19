"""Streaming chat orchestration for guardrailed Q&A over SSE."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import Product
from app.llm.base import LLMMessage, LLMProvider
from app.schemas.chat import ChatClassification
from app.services.chat.conversation_memory import ConversationMemoryService
from app.services.chat.prompt_builder import (
    IngestionContext,
    ProductContext,
    PromptBuildInput,
    ReviewEvidence,
    build_guardrailed_chat_prompt,
)
from app.services.retrieval_service import RetrievedReview, ReviewRetrievalService


@dataclass(frozen=True)
class ChatStreamContext:
    """Resolved chat context before token streaming starts."""

    session_id: UUID
    prompt_messages: list[LLMMessage]
    citations: list[dict[str, Any]]


class ChatStreamService:
    """Coordinates memory, retrieval, prompt-building, and streaming response classification."""

    def __init__(self, db: Session, llm_provider: LLMProvider) -> None:
        self._db = db
        self._llm_provider = llm_provider
        self._memory = ConversationMemoryService(db)
        self._retrieval = ReviewRetrievalService(db)

    def prepare_context(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        question: str,
        session_id: UUID | None,
    ) -> ChatStreamContext:
        memory_ctx = self._memory.get_or_create_context(
            workspace_id=workspace_id,
            product_id=product_id,
            session_id=session_id,
            max_turns=ConversationMemoryService.DEFAULT_MAX_TURNS,
        )

        product = (
            self._db.query(Product)
            .filter(
                Product.id == product_id,
                Product.workspace_id == workspace_id,
            )
            .first()
        )
        if product is None:
            raise ValueError("workspace_id and product_id must reference an existing product context")

        evidence = self._retrieval.retrieve_top_reviews(
            workspace_id=workspace_id,
            product_id=product_id,
            query=question,
            limit=8,
        )

        prompt_payload = PromptBuildInput(
            assistant_role=(
                "You are ReviewLens AI, a guardrailed analyst assistant for product-review intelligence. "
                "Your job is to answer only from ingested review evidence."
            ),
            product=ProductContext(
                product_name=product.name,
                platform=product.platform,
                source_url=product.source_url,
            ),
            ingestion=IngestionContext(
                ingestion_run_id=None,
                records_ingested=_safe_total_reviews(product.stats),
                status=None,
                outcome_code=None,
                summary_snapshot=product.stats,
            ),
            retrieved_reviews=[_to_review_evidence(item) for item in evidence],
            user_question=question,
        )
        prompt = build_guardrailed_chat_prompt(prompt_payload)

        messages: list[LLMMessage] = [LLMMessage(role="system", content=prompt.system_prompt)]
        messages.extend(memory_ctx.recent_messages)
        messages.append(LLMMessage(role="user", content=prompt.user_prompt))

        citations = [_to_citation(index=i + 1, review=item) for i, item in enumerate(evidence)]

        return ChatStreamContext(
            session_id=memory_ctx.session_id,
            prompt_messages=messages,
            citations=citations,
        )

    def stream_answer(self, *, messages: list[LLMMessage], citations: list[dict[str, Any]], question: str) -> list[str]:
        chunks = self._llm_provider.stream_chat(messages=messages, temperature=0.0)
        output: list[str] = []
        for chunk in chunks:
            if chunk.delta:
                output.append(chunk.delta)

        first_pass = "".join(output).strip()
        first_classification = classify_response(first_pass)

        provider_name = getattr(self._llm_provider, "provider_name", "")
        in_scope_question = _question_is_normal_product_analysis(question)
        should_retry = (
            bool(citations)
            and provider_name != "fake"
            and (
                first_classification == ChatClassification.INSUFFICIENT_EVIDENCE
                or (first_classification == ChatClassification.OUT_OF_SCOPE and in_scope_question)
            )
        )
        if not should_retry:
            return output

        retry_messages = list(messages)
        retry_messages.append(
            LLMMessage(
                role="system",
                content=(
                    "Retrieved evidence is available. Provide a best-effort in-scope answer grounded in the evidence. "
                    "Use INSUFFICIENT_EVIDENCE only if evidence is clearly unrelated to the question."
                ),
            )
        )
        retry_messages.append(
            LLMMessage(
                role="user",
                content="Answer directly with concrete findings and cite relevant evidence ids (E1, E2, ...).",
            )
        )

        retry = self._llm_provider.complete_chat(messages=retry_messages, temperature=0.0)
        retry_text = (retry.text or "").strip()
        if retry_text:
            retry_classification = classify_response(retry_text)
            if retry_classification != ChatClassification.INSUFFICIENT_EVIDENCE:
                return _split_tokens_for_stream(retry_text)

        fallback_text = _build_deterministic_citation_answer(question=question, citations=citations)
        if fallback_text:
            return _split_tokens_for_stream(fallback_text)

        return output

    def persist_turn(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        session_id: UUID,
        question: str,
        answer: str,
        classification: ChatClassification,
        citations: list[dict[str, Any]],
    ) -> None:
        self._memory.save_turn(
            workspace_id=workspace_id,
            product_id=product_id,
            session_id=session_id,
            user_message=question,
            assistant_message=answer,
            assistant_is_refusal=classification == ChatClassification.OUT_OF_SCOPE,
            assistant_metadata={
                "classification": classification.value,
                "citations": citations,
            },
        )


def classify_response(text: str) -> ChatClassification:
    normalized = (text or "").strip().upper()
    if normalized.startswith("REFUSAL:"):
        return ChatClassification.OUT_OF_SCOPE
    if normalized.startswith("INSUFFICIENT_EVIDENCE:"):
        return ChatClassification.INSUFFICIENT_EVIDENCE
    return ChatClassification.ANSWER


def format_sse_event(event: str, payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=True)
    return f"event: {event}\\ndata: {data}\\n\\n"


def _split_tokens_for_stream(text: str) -> list[str]:
    tokens = [part for part in text.split(" ") if part]
    if not tokens:
        return []
    return [f"{token} " for token in tokens]


def _question_is_normal_product_analysis(question: str) -> bool:
    text = (question or "").strip().lower()
    if not text:
        return False

    blocked_terms = [
        "competitor",
        "compared to",
        "versus",
        " vs ",
        "g2",
        "trustpilot",
        "amazon",
        "world",
        "industry-wide",
        "market-wide",
        "outside dataset",
    ]
    if any(term in text for term in blocked_terms):
        return False

    return True


def _build_deterministic_citation_answer(*, question: str, citations: list[dict[str, Any]]) -> str:
    if not citations:
        return ""

    evidence_ids = [str(item.get("evidence_id")) for item in citations if item.get("evidence_id")]
    evidence_label = ", ".join(evidence_ids[:4]) if evidence_ids else "available evidence"

    date_range = _extract_date_range(question)
    snippets = [
        str(item.get("snippet") or "").strip()
        for item in citations
        if isinstance(item, dict)
    ]
    snippets = [text for text in snippets if text]
    if not snippets:
        return ""

    if date_range is not None:
        start_date, end_date = date_range
        in_range = _citations_in_date_range(citations=citations, start_date=start_date, end_date=end_date)
        if in_range:
            highlights = _format_highlights(in_range)
            return (
                f"Based on retrieved reviews in the requested period ({start_date.isoformat()} to {end_date.isoformat()}), "
                f"feedback can be summarized from {evidence_label}: {highlights}"
            )

    highlights = _format_highlights(citations)
    return f"Based on retrieved evidence ({evidence_label}), reviewers commonly mention: {highlights}"


def _extract_date_range(question: str) -> tuple[date, date] | None:
    matches = re.findall(r"(\d{4}-\d{2}-\d{2})", question)
    if len(matches) < 2:
        return None

    try:
        first = date.fromisoformat(matches[0])
        second = date.fromisoformat(matches[1])
    except ValueError:
        return None

    if first <= second:
        return first, second
    return second, first


def _citations_in_date_range(*, citations: list[dict[str, Any]], start_date: date, end_date: date) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for item in citations:
        raw_date = item.get("reviewed_at") if isinstance(item, dict) else None
        if not isinstance(raw_date, str) or not raw_date:
            continue
        try:
            reviewed = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if start_date <= reviewed <= end_date:
            selected.append(item)
    return selected


def _format_highlights(citations: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for item in citations[:3]:
        snippet = str(item.get("snippet") or "").strip()
        evidence_id = str(item.get("evidence_id") or "evidence")
        if not snippet:
            continue
        snippet_short = snippet[:160]
        parts.append(f"[{evidence_id}] {snippet_short}")

    if not parts:
        return "the available cited reviews"

    return " | ".join(parts)


def _to_review_evidence(item: RetrievedReview) -> ReviewEvidence:
    return ReviewEvidence(
        review_id=str(item.review_id),
        title=item.title,
        body=item.body,
        rating=item.rating,
        author_name=item.author_name,
        reviewed_at=item.reviewed_at,
        rank=item.rank,
    )


def _to_citation(*, index: int, review: RetrievedReview) -> dict[str, Any]:
    return {
        "evidence_id": f"E{index}",
        "review_id": str(review.review_id),
        "title": review.title,
        "snippet": review.snippet,
        "author_name": review.author_name,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
        "rating": review.rating,
        "rank": review.rank,
    }


def _safe_total_reviews(stats: dict[str, Any] | None) -> int:
    if not isinstance(stats, dict):
        return 0
    value = stats.get("total_reviews", 0)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
