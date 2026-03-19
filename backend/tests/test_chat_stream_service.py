"""Unit tests for chat stream service token/retry behavior."""

from __future__ import annotations

from app.llm.base import LLMChatResult, LLMMessage, LLMStreamChunk
from app.schemas.chat import ChatClassification
from app.services.chat.chat_stream_service import ChatStreamService, classify_response


class _NonFakeRetryProvider:
    provider_name = "openai"

    def stream_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return [
            LLMStreamChunk(provider="openai", model="gpt-test", delta="INSUFFICIENT_EVIDENCE:", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta=" not enough", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta="", done=True),
        ]

    def complete_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return LLMChatResult(
            provider="openai",
            model="gpt-test",
            text="Answer from evidence E1 and E2.",
            raw={},
        )

    def generate_structured(self, *, system_prompt: str, user_prompt: str, model=None, temperature: float = 0.0):
        raise NotImplementedError


class _FakeProviderNoRetry:
    provider_name = "fake"

    def stream_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return [
            LLMStreamChunk(provider="fake", model="fake", delta="INSUFFICIENT_EVIDENCE:", done=False),
            LLMStreamChunk(provider="fake", model="fake", delta=" still insufficient", done=False),
            LLMStreamChunk(provider="fake", model="fake", delta="", done=True),
        ]

    def complete_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return LLMChatResult(provider="fake", model="fake", text="unused", raw={})

    def generate_structured(self, *, system_prompt: str, user_prompt: str, model=None, temperature: float = 0.0):
        raise NotImplementedError


class _NonFakeAlwaysInsufficientProvider:
    provider_name = "openai"

    def stream_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return [
            LLMStreamChunk(provider="openai", model="gpt-test", delta="INSUFFICIENT_EVIDENCE:", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta=" still insufficient", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta="", done=True),
        ]

    def complete_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return LLMChatResult(provider="openai", model="gpt-test", text="INSUFFICIENT_EVIDENCE: retry failed", raw={})

    def generate_structured(self, *, system_prompt: str, user_prompt: str, model=None, temperature: float = 0.0):
        raise NotImplementedError


def test_classify_response_labels_expected_prefixes() -> None:
    assert classify_response("REFUSAL: nope") == ChatClassification.OUT_OF_SCOPE
    assert classify_response("INSUFFICIENT_EVIDENCE: nope") == ChatClassification.INSUFFICIENT_EVIDENCE
    assert classify_response("Plain answer") == ChatClassification.ANSWER


def test_stream_answer_retries_when_non_fake_and_citations_exist() -> None:
    service = ChatStreamService(db=None, llm_provider=_NonFakeRetryProvider())

    tokens = service.stream_answer(
        messages=[LLMMessage(role="user", content="question")],
        citations=[{"evidence_id": "E1"}],
        question="What themes appear most often?",
    )

    text = "".join(tokens).strip()
    assert text == "Answer from evidence E1 and E2."


def test_stream_answer_skips_retry_for_fake_provider() -> None:
    service = ChatStreamService(db=None, llm_provider=_FakeProviderNoRetry())

    tokens = service.stream_answer(
        messages=[LLMMessage(role="user", content="question")],
        citations=[{"evidence_id": "E1"}],
        question="What themes appear most often?",
    )

    text = "".join(tokens).strip()
    assert text.startswith("INSUFFICIENT_EVIDENCE:")


class _NonFakeOutOfScopeProvider:
    provider_name = "openai"

    def stream_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return [
            LLMStreamChunk(provider="openai", model="gpt-test", delta="REFUSAL:", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta=" cannot answer", done=False),
            LLMStreamChunk(provider="openai", model="gpt-test", delta="", done=True),
        ]

    def complete_chat(self, *, messages: list[LLMMessage], model=None, temperature: float = 0.2):
        _ = (messages, model, temperature)
        return LLMChatResult(
            provider="openai",
            model="gpt-test",
            text="Best-effort trend answer grounded in E1.",
            raw={},
        )

    def generate_structured(self, *, system_prompt: str, user_prompt: str, model=None, temperature: float = 0.0):
        raise NotImplementedError


def test_stream_answer_retries_on_out_of_scope_for_in_scope_question() -> None:
    service = ChatStreamService(db=None, llm_provider=_NonFakeOutOfScopeProvider())

    tokens = service.stream_answer(
        messages=[LLMMessage(role="user", content="question")],
        citations=[{"evidence_id": "E1"}],
        question="How did reviewer feedback change over time?",
    )

    text = "".join(tokens).strip()
    assert text == "Best-effort trend answer grounded in E1."


def test_stream_answer_uses_deterministic_fallback_when_retry_still_insufficient() -> None:
    service = ChatStreamService(db=None, llm_provider=_NonFakeAlwaysInsufficientProvider())

    tokens = service.stream_answer(
        messages=[LLMMessage(role="user", content="question")],
        citations=[
            {
                "evidence_id": "E1",
                "snippet": "Training and setup were pleasant and support was responsive.",
                "reviewed_at": "2021-01-15",
            },
            {
                "evidence_id": "E2",
                "snippet": "Easy publishing and no-code workflow saved the team time.",
                "reviewed_at": "2021-08-09",
            },
        ],
        question="How did feedback change between 2020-05-20 and 2021-10-07?",
    )

    text = "".join(tokens).strip()
    assert text.startswith("Based on retrieved reviews in the requested period")
    assert "[E1]" in text
