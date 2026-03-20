"""Unit tests for guardrailed Q&A prompt builder."""

from __future__ import annotations

from datetime import date

from app.services.chat.prompt_builder import (
    IngestionContext,
    ProductContext,
    PromptBuildInput,
    ReviewEvidence,
    build_guardrailed_chat_prompt,
)


def _build_payload(*, question: str = "What do users say about onboarding?") -> PromptBuildInput:
    return PromptBuildInput(
        assistant_role="You are ReviewLens AI, an ORM analyst assistant.",
        product=ProductContext(
            product_name="PressPage",
            platform="generic_source",
            source_url="https://www.reviews.example.com/p/164876/PressPage/reviews/",
        ),
        ingestion=IngestionContext(
            ingestion_run_id="run-123",
            records_ingested=42,
            status="success",
            outcome_code="ok",
            summary_snapshot={"total_reviews": 42, "average_rating": 4.3},
        ),
        retrieved_reviews=[
            ReviewEvidence(
                review_id="review-1",
                title="Strong onboarding",
                body="Onboarding was smooth and customer support replied quickly.",
                rating=5.0,
                author_name="Ari",
                reviewed_at=date(2026, 3, 1),
                rank=0.91,
            ),
            ReviewEvidence(
                review_id="review-2",
                title="Good support",
                body="Support was helpful but reporting needs improvement.",
                rating=4.0,
                author_name="Sam",
                reviewed_at=date(2026, 3, 4),
                rank=0.72,
            ),
        ],
        user_question=question,
    )


def test_prompt_builder_includes_identity_context_and_evidence_sections() -> None:
    result = build_guardrailed_chat_prompt(_build_payload())

    assert "[ASSISTANT_ROLE]" in result.system_prompt
    assert "[SELECTED_SCOPE]" in result.system_prompt
    assert "Product: PressPage" in result.system_prompt
    assert "Platform: generic_source" in result.system_prompt
    assert "Canonical source URL: https://www.reviews.example.com/p/164876/PressPage/reviews/" in result.system_prompt

    assert "[RETRIEVED_EVIDENCE]" in result.system_prompt
    assert "E1" in result.system_prompt
    assert "E2" in result.system_prompt
    assert "review_id=review-1" in result.system_prompt
    assert "Onboarding was smooth" in result.system_prompt


def test_prompt_builder_contains_explicit_scope_refusal_and_insufficient_rules() -> None:
    result = build_guardrailed_chat_prompt(_build_payload())

    assert "Do not answer about other platforms, competitors, or market-wide trends" in result.system_prompt
    assert "Do not use external or general world knowledge" in result.system_prompt
    assert "[REFUSAL_BEHAVIOR]" in result.system_prompt
    assert "REFUSAL: I can only answer from the ingested reviews" in result.system_prompt
    assert "[INSUFFICIENT_EVIDENCE_BEHAVIOR]" in result.system_prompt
    assert "INSUFFICIENT_EVIDENCE: The ingested reviews provided do not contain enough evidence" in result.system_prompt


def test_prompt_builder_handles_no_evidence_with_clear_audit_text() -> None:
    payload = _build_payload()
    payload = PromptBuildInput(
        assistant_role=payload.assistant_role,
        product=payload.product,
        ingestion=payload.ingestion,
        retrieved_reviews=[],
        user_question=payload.user_question,
    )

    result = build_guardrailed_chat_prompt(payload)

    assert "No retrieved evidence items were provided." in result.system_prompt
    assert "Summary total reviews: 42" in result.system_prompt


def test_prompt_builder_is_deterministic_and_pure() -> None:
    payload = _build_payload()

    result_one = build_guardrailed_chat_prompt(payload)
    result_two = build_guardrailed_chat_prompt(payload)

    assert result_one == result_two


def test_prompt_builder_preserves_user_question_in_user_prompt() -> None:
    result = build_guardrailed_chat_prompt(_build_payload(question="Compare this with G2 competitors"))

    assert "[USER_QUESTION]" in result.user_prompt
    assert "Compare this with G2 competitors" in result.user_prompt
    assert "Answer the user using the system rules above." in result.user_prompt

