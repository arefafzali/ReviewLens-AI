"""Tests for Firecrawl fetch provider behavior."""

from __future__ import annotations

import httpx

from app.llm.fake_provider import FakeLLMProvider
from app.services.ingestion.fetchers.firecrawl import FirecrawlFetcher


def test_firecrawl_fetch_success_with_realistic_fixture(monkeypatch, read_fixture_text, read_fixture_json) -> None:
    html_fixture = read_fixture_text("html/capterra_presspage_reviews_sample.html")
    markdown_fixture = read_fixture_text("markdown/capterra_presspage_reviews_sample.md")
    extracted_payload = read_fixture_json("json/capterra_extracted_reviews_sample.json")

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            status_code=200,
            json={
                "success": True,
                "data": {
                    "html": html_fixture,
                    "markdown": markdown_fixture,
                    "metadata": {"sourceURL": "https://example.com/reviews"},
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.ingestion.fetchers.firecrawl.httpx.post", fake_post)

    llm_provider = FakeLLMProvider(
        structured_response=extracted_payload
    )

    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        llm_provider=llm_provider,
        llm_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is True
    assert result.provider == "firecrawl"
    assert result.status_code == 200
    assert result.final_url == "https://example.com/reviews"
    assert "onboarding team was responsive" in (result.body or "").lower()
    assert result.metadata["gpt_extracted_reviews"] == 3
    assert result.metadata["chunk_count"] >= 1


def test_firecrawl_fetch_config_error_without_api_key() -> None:
    llm_provider = FakeLLMProvider()
    fetcher = FirecrawlFetcher(
        firecrawl_api_key=None,
        llm_provider=llm_provider,
        llm_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "config_error"
    assert "firecrawl_api_key" in (result.error_detail or "").lower()


def test_firecrawl_fetch_config_error_without_llm_provider() -> None:
    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        llm_provider=None,
        llm_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "config_error"
    assert "llm provider" in (result.error_detail or "").lower()


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
        llm_provider=FakeLLMProvider(),
        llm_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is False
    assert result.error_code.value == "upstream_error"
    assert "provider failure" in (result.error_detail or "").lower()


def test_firecrawl_fetch_dedupes_same_body_author_from_fixture_payload(monkeypatch, read_fixture_text, read_fixture_json) -> None:
    markdown_fixture = read_fixture_text("markdown/capterra_presspage_reviews_sample.md")
    extracted_payload = read_fixture_json("json/capterra_extracted_reviews_sample.json")

    def fake_post(url, headers=None, json=None, timeout=None):
        return httpx.Response(
            status_code=200,
            json={
                "success": True,
                "data": {
                    "html": "<html><body><h1>fixture</h1></body></html>",
                    "markdown": markdown_fixture,
                    "metadata": {"sourceURL": "https://example.com/reviews"},
                },
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("app.services.ingestion.fetchers.firecrawl.httpx.post", fake_post)

    fetcher = FirecrawlFetcher(
        firecrawl_api_key="firecrawl-key",
        llm_provider=FakeLLMProvider(structured_response=extracted_payload),
        llm_model="gpt-4o-mini",
    )
    result = fetcher.fetch("https://example.com/reviews")

    assert result.ok is True
    assert result.metadata["gpt_extracted_reviews"] == 3
    assert "duplicate" not in (result.body or "").lower()
