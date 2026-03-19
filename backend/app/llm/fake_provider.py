"""Deterministic fake LLM provider for tests and local simulations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.llm.base import LLMChatResult, LLMMessage, LLMStreamChunk, LLMStructuredResult


class FakeLLMProvider:
    """Simple deterministic provider that avoids network calls."""

    provider_name = "fake"

    def __init__(
        self,
        *,
        model: str = "fake-llm-v1",
        chat_response: str = "deterministic fake response",
        structured_response: Any = None,
    ) -> None:
        self._model = model
        self._chat_response = chat_response
        self._structured_response = structured_response if structured_response is not None else {"reviews": []}

    def complete_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> LLMChatResult:
        _ = (messages, temperature)
        return LLMChatResult(
            provider=self.provider_name,
            model=model or self._model,
            text=self._chat_response,
            raw={"provider": self.provider_name},
        )

    def stream_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> list[LLMStreamChunk]:
        _ = (messages, temperature)
        output_model = model or self._model
        tokens = [token for token in self._chat_response.split(" ") if token]

        chunks = [
            LLMStreamChunk(provider=self.provider_name, model=output_model, delta=f"{token} ", done=False)
            for token in tokens
        ]
        chunks.append(LLMStreamChunk(provider=self.provider_name, model=output_model, delta="", done=True))
        return chunks

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMStructuredResult:
        _ = (system_prompt, user_prompt, temperature)
        payload = deepcopy(self._structured_response)
        return LLMStructuredResult(
            provider=self.provider_name,
            model=model or self._model,
            payload=payload,
            text=None,
            raw={"provider": self.provider_name},
        )
