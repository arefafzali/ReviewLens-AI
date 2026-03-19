"""OpenAI implementation of the provider-agnostic LLM contract."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.llm.base import LLMChatResult, LLMMessage, LLMProviderError, LLMStreamChunk, LLMStructuredResult


class OpenAIProvider:
    """OpenAI chat-completions adapter behind the internal LLM contract."""

    provider_name = "openai"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float = 45.0) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or "gpt-4o-mini"
        self._timeout_seconds = timeout_seconds

    def complete_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> LLMChatResult:
        payload = {
            "model": model or self._model,
            "temperature": temperature,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        }
        response_json = self._request_chat(payload=payload)
        content = _extract_message_content(response_json) or ""

        return LLMChatResult(
            provider=self.provider_name,
            model=(response_json.get("model") if isinstance(response_json, dict) else None),
            text=content,
            raw=response_json if isinstance(response_json, dict) else {},
        )

    def stream_chat(
        self,
        *,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.2,
    ) -> list[LLMStreamChunk]:
        payload = {
            "model": model or self._model,
            "temperature": temperature,
            "stream": True,
            "messages": [{"role": item.role, "content": item.content} for item in messages],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            ) as response:
                if response.status_code >= 400:
                    raise LLMProviderError(_response_detail(response=response, default_message="OpenAI request failed."))

                chunks: list[LLMStreamChunk] = []
                model_name: str | None = None
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        chunks.append(
                            LLMStreamChunk(
                                provider=self.provider_name,
                                model=model_name,
                                delta="",
                                done=True,
                            )
                        )
                        break

                    try:
                        payload_json = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    if model_name is None and isinstance(payload_json, dict):
                        candidate = payload_json.get("model")
                        if isinstance(candidate, str):
                            model_name = candidate

                    delta_text = _extract_delta_text(payload_json)
                    if delta_text:
                        chunks.append(
                            LLMStreamChunk(
                                provider=self.provider_name,
                                model=model_name,
                                delta=delta_text,
                                done=False,
                            )
                        )

                if chunks and not chunks[-1].done:
                    chunks.append(
                        LLMStreamChunk(
                            provider=self.provider_name,
                            model=model_name,
                            delta="",
                            done=True,
                        )
                    )
                return chunks
        except httpx.HTTPError as exc:
            raise LLMProviderError(str(exc)) from exc

    def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
        temperature: float = 0.0,
    ) -> LLMStructuredResult:
        payload = {
            "model": model or self._model,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        response_json = self._request_chat(payload=payload)
        content = _extract_message_content(response_json)
        parsed = _parse_json_text(content) if content else None

        return LLMStructuredResult(
            provider=self.provider_name,
            model=(response_json.get("model") if isinstance(response_json, dict) else None),
            payload=parsed,
            text=content,
            raw=response_json if isinstance(response_json, dict) else {},
        )

    def _request_chat(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise LLMProviderError(str(exc)) from exc

        if response.status_code >= 400:
            raise LLMProviderError(_response_detail(response=response, default_message="OpenAI request failed."))

        parsed = _safe_json(response)
        if not isinstance(parsed, dict):
            raise LLMProviderError("OpenAI response was not valid JSON.")
        return parsed


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None


def _response_detail(*, response: httpx.Response, default_message: str) -> str:
    payload = _safe_json(response)
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(error, str) and error.strip():
            return error.strip()
        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    text = (response.text or "").strip()
    if text:
        return text[:300]
    return default_message


def _extract_message_content(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None

    content = message.get("content")
    if isinstance(content, str):
        return content.strip() or None

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        joined = "\n".join(part.strip() for part in parts if part.strip())
        return joined or None

    return None


def _extract_delta_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    delta = first.get("delta")
    if not isinstance(delta, dict):
        return ""

    content = delta.get("content")
    return content if isinstance(content, str) else ""


def _parse_json_text(text: str) -> Any:
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            candidate = raw[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                return None
        return None
