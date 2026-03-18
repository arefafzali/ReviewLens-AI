"""Generic URL ingestion pipeline that combines fetching and source parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.schemas.ingestion import IngestionOutcomeCode, IngestionRunStatus
from app.services.ingestion.fetchers.base import FetchFailureCode, PublicUrlFetcher
from app.services.ingestion.fetchers.firecrawl import FirecrawlFetcher
from app.services.ingestion.url_safety import validate_public_fetch_url


@dataclass(frozen=True)
class URLIngestionPipelineResult:
    """Structured URL ingestion pipeline outcome."""

    status: IngestionRunStatus
    outcome_code: IngestionOutcomeCode
    captured_reviews: int
    message: str
    warnings: list[str]
    error_detail: str | None
    diagnostics: dict[str, Any]
    extracted_reviews: list[dict[str, Any]] = field(default_factory=list)


class URLIngestionPipeline:
    """Coordinates Firecrawl+GPT URL ingestion for review extraction."""

    def __init__(
        self,
        *,
        fetcher: PublicUrlFetcher,
    ) -> None:
        self._fetcher = fetcher

    @classmethod
    def with_firecrawl(
        cls,
        *,
        firecrawl_api_key: str | None,
        openai_api_key: str | None,
        openai_model: str,
        firecrawl_timeout_seconds: float,
        openai_timeout_seconds: float,
        chunk_size_chars: int,
        chunk_overlap_chars: int,
        max_chunks: int,
    ) -> "URLIngestionPipeline":
        fetcher = FirecrawlFetcher(
            firecrawl_api_key=firecrawl_api_key,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            firecrawl_timeout_seconds=firecrawl_timeout_seconds,
            openai_timeout_seconds=openai_timeout_seconds,
            chunk_size_chars=chunk_size_chars,
            chunk_overlap_chars=chunk_overlap_chars,
            max_chunks=max_chunks,
        )
        return cls(fetcher=fetcher)

    def run(self, target_url: str) -> URLIngestionPipelineResult:
        source_host = _source_host_for_url(target_url)

        try:
            validate_public_fetch_url(target_url)
        except ValueError as exc:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.FAILED,
                outcome_code=IngestionOutcomeCode.INVALID_URL,
                captured_reviews=0,
                message="URL is not allowed for public ingestion.",
                warnings=[],
                error_detail=str(exc),
                diagnostics={
                    "failure_stage": "validation",
                    "provider": self._fetcher.provider_name,
                    "requested_url": target_url,
                    "source_host": source_host,
                },
                extracted_reviews=[],
            )

        fetch_result = self._fetcher.fetch(target_url)
        if not fetch_result.ok:
            return self._fetch_failure_result(
                source_host=source_host,
                requested_url=target_url,
                fetch_result=fetch_result,
            )

        pages_scraped = 1
        last_status = fetch_result.status_code
        effective_url = fetch_result.final_url or target_url
        source_host = _source_host_for_url(effective_url)

        metadata = fetch_result.metadata or {}
        extracted_reviews = metadata.get("extracted_reviews")
        if isinstance(extracted_reviews, list):
            extracted = [item for item in extracted_reviews if isinstance(item, dict)]
            captured_reviews = len(extracted)
        else:
            extracted = []
            captured_reviews = _safe_int(metadata.get("gpt_extracted_reviews"))

        diagnostics = {
            "failure_stage": None,
            "provider": fetch_result.provider,
            "requested_url": target_url,
            "final_url": effective_url,
            "fetch_status": last_status,
            "source_host": source_host,
            "parser": "gpt_markdown_chunks",
            "pages_scraped": pages_scraped,
            "chunk_count": _safe_int(metadata.get("chunk_count")),
            "gpt_extracted_reviews": captured_reviews,
            "gpt_model": metadata.get("gpt_model"),
        }

        if captured_reviews == 0:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=0,
                message="Ingestion completed but no review records were captured.",
                warnings=["No reviews were extracted from markdown chunks."],
                error_detail=None,
                diagnostics=diagnostics,
                extracted_reviews=extracted,
            )

        if captured_reviews < 3:
            return URLIngestionPipelineResult(
                status=IngestionRunStatus.PARTIAL,
                outcome_code=IngestionOutcomeCode.LOW_DATA,
                captured_reviews=captured_reviews,
                message="Ingestion completed with limited captured reviews.",
                warnings=["Low review count detected from markdown extraction."],
                error_detail=None,
                diagnostics=diagnostics,
                extracted_reviews=extracted,
            )

        return URLIngestionPipelineResult(
            status=IngestionRunStatus.SUCCESS,
            outcome_code=IngestionOutcomeCode.OK,
            captured_reviews=captured_reviews,
            message="Ingestion completed successfully.",
            warnings=[],
            error_detail=None,
            diagnostics=diagnostics,
            extracted_reviews=extracted,
        )

    def _fetch_failure_result(
        self,
        *,
        source_host: str,
        requested_url: str,
        fetch_result,
    ) -> URLIngestionPipelineResult:
        if fetch_result.error_code == FetchFailureCode.BLOCKED:
            outcome = IngestionOutcomeCode.BLOCKED
            message = "Ingestion request was blocked by source constraints."
        elif fetch_result.error_code == FetchFailureCode.CONFIG_ERROR:
            outcome = IngestionOutcomeCode.PARSE_FAILED
            message = "Fetch provider is not configured correctly."
        else:
            outcome = IngestionOutcomeCode.PARSE_FAILED
            message = "Source content could not be retrieved for parsing."

        return URLIngestionPipelineResult(
            status=IngestionRunStatus.FAILED,
            outcome_code=outcome,
            captured_reviews=0,
            message=message,
            warnings=[],
            error_detail=fetch_result.error_detail,
            diagnostics={
                "failure_stage": "fetch",
                "provider": fetch_result.provider,
                "requested_url": requested_url,
                "final_url": fetch_result.final_url,
                "fetch_status": fetch_result.status_code,
                "source_host": source_host,
                "parser": "gpt_markdown_chunks",
                "pages_scraped": 0,
                "fetch_error_code": fetch_result.error_code.value if fetch_result.error_code else None,
                "fetch_metadata": fetch_result.metadata,
            },
            extracted_reviews=[],
        )


def _source_host_for_url(url: str) -> str:
    host = (urlparse(url).netloc or "").split(":", 1)[0].lower()
    return host


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
