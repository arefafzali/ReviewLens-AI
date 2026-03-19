"""Factory for selecting configured LLM provider adapters."""

from __future__ import annotations

import json
from typing import Any

from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.fake_provider import FakeLLMProvider
from app.llm.openai_provider import OpenAIProvider


def build_llm_provider(settings: Settings) -> LLMProvider | None:
    """Return the configured provider instance, or None if missing credentials."""

    provider = (settings.llm_provider or "openai").strip().lower()

    if provider == "openai":
        api_key = (settings.openai_api_key or "").strip()
        if not api_key:
            return None
        return OpenAIProvider(
            api_key=api_key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )

    if provider == "fake":
        structured = _parse_fake_structured_response(settings.llm_fake_structured_response)
        return FakeLLMProvider(
            model=settings.openai_model,
            structured_response=structured,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


def _parse_fake_structured_response(raw: str | None) -> Any:
    if raw is None or not raw.strip():
        return {"reviews": []}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("REVIEWLENS_LLM_FAKE_STRUCTURED_RESPONSE must be valid JSON") from exc

    return parsed
