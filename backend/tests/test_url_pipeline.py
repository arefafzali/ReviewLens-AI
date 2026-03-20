"""Tests for generic URL ingestion pipeline behavior and diagnostics."""

from __future__ import annotations

from app.services.ingestion.fetchers.base import FetchFailureCode, FetchResult, PublicUrlFetcher
from app.services.ingestion.url_pipeline import URLIngestionPipeline


class _BlockedFetcher(PublicUrlFetcher):
    provider_name = "firecrawl"

    def fetch(self, target_url: str) -> FetchResult:
        return FetchResult(
            ok=False,
            provider=self.provider_name,
            requested_url=target_url,
            final_url=target_url,
            status_code=403,
            body=None,
            error_code=FetchFailureCode.BLOCKED,
            error_detail="HTTP 403",
            metadata={"upstream_status": 403},
        )


class _SuccessNoReviewsFetcher(PublicUrlFetcher):
    provider_name = "firecrawl"

    def fetch(self, target_url: str) -> FetchResult:
        return FetchResult(
            ok=True,
            provider=self.provider_name,
            requested_url=target_url,
            final_url=target_url,
            status_code=200,
            body=None,
            metadata={"chunk_count": 4, "gpt_extracted_reviews": 0, "gpt_model": "gpt-4o-mini"},
        )


def test_pipeline_classifies_blocked_fetch_with_diagnostics() -> None:
    pipeline = URLIngestionPipeline(fetcher=_BlockedFetcher())

    result = pipeline.run("https://www.reviews.example.com/p/164876/PressPage/reviews/")

    assert result.status.value == "failed"
    assert result.outcome_code.value == "blocked"
    assert result.diagnostics["failure_stage"] == "fetch"
    assert result.diagnostics["provider"] == "firecrawl"
    assert result.diagnostics["fetch_status"] == 403


def test_pipeline_handles_unknown_host_with_gpt_chunk_extraction(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )

    pipeline = URLIngestionPipeline(fetcher=_SuccessNoReviewsFetcher())
    result = pipeline.run("https://www.g2.com/products/example/reviews")

    assert result.status.value == "partial"
    assert result.outcome_code.value == "low_data"
    assert result.diagnostics["failure_stage"] is None
    assert result.diagnostics["source_host"] == "www.g2.com"
    assert result.diagnostics["parser"] == "gpt_markdown_chunks"
    assert result.diagnostics["gpt_extracted_reviews"] == 0

