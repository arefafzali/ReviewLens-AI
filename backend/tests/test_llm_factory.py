"""Tests for LLM provider factory selection and deterministic fake provider behavior."""

from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.llm.factory import build_llm_provider
from app.llm.fake_provider import FakeLLMProvider
from app.llm.openai_provider import OpenAIProvider


def _settings(**overrides) -> SimpleNamespace:
    base = {
        "llm_provider": "openai",
        "openai_api_key": "test-openai-key",
        "openai_model": "gpt-4o-mini",
        "openai_timeout_seconds": 45.0,
        "llm_fake_structured_response": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_factory_selects_openai_provider() -> None:
    settings = _settings(llm_provider="openai", openai_api_key="secret")

    provider = build_llm_provider(settings)

    assert isinstance(provider, OpenAIProvider)


def test_factory_returns_none_when_openai_key_missing() -> None:
    settings = _settings(llm_provider="openai", openai_api_key="")

    provider = build_llm_provider(settings)

    assert provider is None


def test_factory_selects_fake_provider_with_deterministic_payload() -> None:
    settings = _settings(
        llm_provider="fake",
        openai_api_key="",
        llm_fake_structured_response='{"reviews":[{"body":"deterministic"}]}',
    )

    provider = build_llm_provider(settings)

    assert isinstance(provider, FakeLLMProvider)
    result = provider.generate_structured(
        system_prompt="sys",
        user_prompt="user",
    )
    assert result.payload == {"reviews": [{"body": "deterministic"}]}


def test_factory_rejects_invalid_provider() -> None:
    settings = _settings(llm_provider="unsupported")

    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        build_llm_provider(settings)


def test_factory_rejects_invalid_fake_json_payload() -> None:
    settings = _settings(
        llm_provider="fake",
        llm_fake_structured_response="{invalid-json",
        openai_api_key="",
    )

    with pytest.raises(ValueError, match="must be valid JSON"):
        build_llm_provider(settings)
