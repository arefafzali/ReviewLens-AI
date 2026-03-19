"""Provider-agnostic contracts for LLM chat, structured generation, and streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider request fails."""


@dataclass(frozen=True)
class LLMMessage:
    """Normalized chat message contract used by all providers."""

    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMChatResult:
    """Normalized non-stream chat completion response."""

    provider: str
    model: str | None
    text: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMStructuredResult:
    """Normalized structured-generation response."""

    provider: str
    model: str | None
    payload: Any
    text: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMStreamChunk:
    """One streaming token/update from a provider."""

    provider: str
    model: str | None
    delta: str
    done: bool = False


class LLMProvider(Protocol):
    """Unified provider contract used by business services."""

    provider_name: str

    def complete_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> LLMChatResult:
        """Run non-streaming chat completion."""

    def stream_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> list[LLMStreamChunk]:
        """Run streaming chat completion and return ordered chunks."""

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMStructuredResult:
        """Run structured generation and return normalized output."""
