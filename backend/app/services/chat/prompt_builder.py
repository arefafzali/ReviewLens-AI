"""Pure prompt-building service for guardrailed, review-grounded Q&A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class ProductContext:
    """Identity context for the currently selected analysis target."""

    product_name: str
    platform: str
    source_url: str | None = None


@dataclass(frozen=True)
class IngestionContext:
    """Source capture context used to ground guardrails and confidence."""

    ingestion_run_id: str | None
    records_ingested: int
    status: str | None = None
    outcome_code: str | None = None
    summary_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True)
class ReviewEvidence:
    """One retrieved review item provided to the chat prompt."""

    review_id: str
    body: str
    title: str | None = None
    rating: float | None = None
    author_name: str | None = None
    reviewed_at: date | None = None
    rank: float | None = None


@dataclass(frozen=True)
class PromptBuildInput:
    """Input contract for building guardrailed chat prompts."""

    assistant_role: str
    product: ProductContext
    ingestion: IngestionContext
    retrieved_reviews: list[ReviewEvidence]
    user_question: str


@dataclass(frozen=True)
class PromptBuildResult:
    """Output contract for LLM chat prompt payloads."""

    system_prompt: str
    user_prompt: str


def build_guardrailed_chat_prompt(payload: PromptBuildInput) -> PromptBuildResult:
    """Build deterministic, auditable prompt text for guarded review Q&A.

    This builder is intentionally pure and side-effect free. It only formats
    provided inputs into explicit system and user prompts.
    """

    system_prompt = _build_system_prompt(payload)
    user_prompt = _build_user_prompt(payload)
    return PromptBuildResult(system_prompt=system_prompt, user_prompt=user_prompt)


def _build_system_prompt(payload: PromptBuildInput) -> str:
    product_name = payload.product.product_name.strip()
    platform = payload.product.platform.strip().lower()
    source_url = (payload.product.source_url or "").strip() or "unknown"

    ingestion = payload.ingestion
    run_id = (ingestion.ingestion_run_id or "unknown").strip() or "unknown"
    status = (ingestion.status or "unknown").strip() or "unknown"
    outcome = (ingestion.outcome_code or "unknown").strip() or "unknown"

    summary = ingestion.summary_snapshot if isinstance(ingestion.summary_snapshot, dict) else {}
    total_reviews = _safe_int(summary.get("total_reviews"), fallback=ingestion.records_ingested)
    average_rating = _safe_float(summary.get("average_rating"))

    evidence_section = _format_evidence(payload.retrieved_reviews)

    average_rating_str = f"{average_rating:.2f}" if average_rating is not None else "unknown"

    return "\n".join(
        [
            "[ASSISTANT_ROLE]",
            payload.assistant_role.strip(),
            "",
            "[SELECTED_SCOPE]",
            f"- Product: {product_name}",
            f"- Platform: {platform}",
            f"- Canonical source URL: {source_url}",
            "",
            "[INGESTION_CONTEXT]",
            f"- Ingestion run id: {run_id}",
            f"- Ingestion status: {status}",
            f"- Ingestion outcome: {outcome}",
            f"- Total ingested reviews in scope: {ingestion.records_ingested}",
            f"- Summary total reviews: {total_reviews}",
            f"- Summary average rating: {average_rating_str}",
            "",
            "[RETRIEVED_EVIDENCE]",
            evidence_section,
            "",
            "[SCOPE_GUARD_RULES]",
            "1. Answer only using the retrieved evidence and ingestion context in this prompt.",
            f"2. Treat {product_name} on {platform} as the only allowed analysis target.",
            "3. Do not answer about other platforms, competitors, or market-wide trends unless they are explicitly present in the retrieved evidence text.",
            "4. Do not use external or general world knowledge, prior assumptions, or unstated facts.",
            "5. Questions about normal product analysis (themes, strengths, weaknesses, rating drivers, and change over time) are in-scope when they refer to the selected product/platform.",
            "5. If the question asks for information outside scope, refuse and redirect to in-scope analysis.",
            "",
            "[REFUSAL_BEHAVIOR]",
            "If out of scope, answer with this exact format:",
            "REFUSAL: I can only answer from the ingested reviews for the selected product/platform.",
            "REASON: Briefly state which part is out of scope.",
            "NEXT_STEP: Suggest a revised in-scope question grounded in available reviews.",
            "",
            "[INSUFFICIENT_EVIDENCE_BEHAVIOR]",
            "If evidence is insufficient or absent, answer with this exact format:",
            "INSUFFICIENT_EVIDENCE: The ingested reviews provided do not contain enough evidence to answer confidently.",
            "WHAT_IS_MISSING: List the missing evidence needed.",
            "NEXT_STEP: Ask for a narrower question or more review data from the same selected product/platform.",
            "Use INSUFFICIENT_EVIDENCE only when retrieved evidence is empty or clearly unrelated to the question.",
            "If question is in-scope but evidence is partial (for example trend over time with sparse dates), provide a best-effort answer with caveats instead of REFUSAL.",
            "",
            "[ANSWER_REQUIREMENTS]",
            "- Keep answers concise and specific.",
            "- Cite evidence ids (for example: E1, E2) when making factual claims.",
            "- If one or more evidence items are provided, give a best-effort answer from those items before considering INSUFFICIENT_EVIDENCE.",
            "- If evidence conflicts, state the conflict and avoid overclaiming.",
            "- Never fabricate quotes, ratings, dates, or counts.",
        ]
    )


def _build_user_prompt(payload: PromptBuildInput) -> str:
    question = payload.user_question.strip()
    if not question:
        question = "(no question provided)"

    return "\n".join(
        [
            "[USER_QUESTION]",
            question,
            "",
            "[INSTRUCTION]",
            "Answer the user using the system rules above.",
        ]
    )


def _format_evidence(items: list[ReviewEvidence]) -> str:
    if not items:
        return "- No retrieved evidence items were provided."

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        label = f"E{index}"
        title = _clean(item.title) or "(untitled)"
        body = _clean(item.body) or "(empty body)"
        author = _clean(item.author_name) or "unknown"
        rating = f"{item.rating:.2f}" if item.rating is not None else "unknown"
        reviewed_at = item.reviewed_at.isoformat() if item.reviewed_at else "unknown"
        rank = f"{item.rank:.3f}" if item.rank is not None else "unknown"

        lines.append(f"- {label} | review_id={_clean(item.review_id) or 'unknown'} | rank={rank}")
        lines.append(f"  title: {title}")
        lines.append(f"  author: {author} | rating: {rating} | reviewed_at: {reviewed_at}")
        lines.append(f"  body: {body[:600]}")

    return "\n".join(lines)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(fallback)


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
