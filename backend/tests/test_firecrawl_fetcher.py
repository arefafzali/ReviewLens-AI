"""Tests for Firecrawl fetch provider behavior."""

from __future__ import annotations

import httpx

from app.services.ingestion.fetchers.firecrawl import FirecrawlFetcher


def test_firecrawl_fetch_success(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/v1/chat/completions"):
            return httpx.Response(
                status_code=200,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": '{"reviews":[{"title":"Solid product","body":"Very useful for our workflow","rating":4.0,"author":"Riya","date":"2026-03-01","url":"https://example.com/r/1"}]}'
                            }
                        }
                    ]
                },
                request=httpx.Request("POST", url),
            )

        return httpx.Response(
            status_code=200,
            json={
                "success": True,
                "data": {
                    "html": "<html><body><h1>Example Reviews</h1></body></html>",
                    "markdown": "## Reviews\nGreat review text here",
                    "metadata": {"sourceURL": "https://example.com/reviews"},
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.ingestion.fetchers.firecrawl.httpx.post", fake_post)

    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        openai_api_key="openai-key",
        openai_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is True
    assert result.provider == "firecrawl"
    assert result.status_code == 200
    assert result.final_url == "https://example.com/reviews"
    assert "Very useful for our workflow" in (result.body or "")
    assert result.metadata["gpt_extracted_reviews"] == 1


def test_firecrawl_fetch_config_error_without_api_key() -> None:
    fetcher = FirecrawlFetcher(
        firecrawl_api_key=None,
        openai_api_key="openai-key",
        openai_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "config_error"
    assert "firecrawl_api_key" in (result.error_detail or "").lower()


def test_firecrawl_fetch_config_error_without_openai_key() -> None:
    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        openai_api_key=None,
        openai_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "config_error"
    assert "openai_api_key" in (result.error_detail or "").lower()


def test_firecrawl_fetch_surfaces_upstream_error(monkeypatch) -> None:
    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            status_code=500,
            json={"error": "provider failure"},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.ingestion.fetchers.firecrawl.httpx.post", fake_post)

    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        openai_api_key="openai-key",
        openai_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "upstream_error"
    assert "provider failure" in (result.error_detail or "").lower()
