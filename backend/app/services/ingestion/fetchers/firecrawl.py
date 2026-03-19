"""Firecrawl markdown fetch + GPT chunk extraction provider."""

from __future__ import annotations

import html
from typing import Any

import httpx

from app.llm.base import LLMProvider, LLMProviderError
from app.services.ingestion.fetchers.base import FetchFailureCode, FetchResult, PublicUrlFetcher


class FirecrawlFetcher(PublicUrlFetcher):
    """Fetch markdown via Firecrawl and extract reviews via GPT per chunk."""

    provider_name = "firecrawl"

    def __init__(
        self,
        *,
        firecrawl_api_key: str | None,
        llm_provider: LLMProvider | None,
        llm_model: str,
        firecrawl_timeout_seconds: float = 45.0,
        chunk_size_chars: int = 6000,
        chunk_overlap_chars: int = 800,
        max_chunks: int = 30,
    ) -> None:
        self._firecrawl_api_key = (firecrawl_api_key or "").strip()
        self._llm_provider = llm_provider
        self._llm_model = llm_model.strip() or "gpt-4o-mini"
        self._firecrawl_timeout_seconds = firecrawl_timeout_seconds
        self._chunk_size_chars = max(500, chunk_size_chars)
        self._chunk_overlap_chars = max(0, chunk_overlap_chars)
        self._max_chunks = max(1, max_chunks)

    def fetch(self, target_url: str) -> FetchResult:
        if not self._firecrawl_api_key:
            return self._config_error(target_url, "FIRECRAWL_API_KEY is not configured.")
        if self._llm_provider is None:
            return self._config_error(target_url, "Configured LLM provider is not available.")

        scrape_response = self._firecrawl_scrape(target_url)
        if not scrape_response.ok:
            return scrape_response

        markdown = (scrape_response.metadata.get("firecrawl_markdown") or "").strip()
        html_body = (scrape_response.body or "").strip()

        chunks = self._chunk_markdown(markdown)
        extracted_reviews = self._extract_reviews_from_chunks(target_url=target_url, chunks=chunks)

        synthetic_html = self._reviews_to_synthetic_html(extracted_reviews)
        combined_html = "\n".join(part for part in [synthetic_html, html_body] if part)
        if not combined_html:
            combined_html = "<html><body></body></html>"

        metadata = dict(scrape_response.metadata)
        metadata.update(
            {
                "chunk_count": len(chunks),
                "gpt_extracted_reviews": len(extracted_reviews),
                "extracted_reviews": extracted_reviews,
                "gpt_model": self._llm_model,
                "llm_provider": self._llm_provider.provider_name,
            }
        )

        return FetchResult(
            ok=True,
            provider=self.provider_name,
            requested_url=target_url,
            final_url=scrape_response.final_url,
            status_code=scrape_response.status_code,
            body=combined_html,
            metadata=metadata,
        )

    def _firecrawl_scrape(self, target_url: str) -> FetchResult:
        headers = {
            "Authorization": f"Bearer {self._firecrawl_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "url": target_url,
            "formats": ["markdown", "html"],
            "onlyMainContent": False,
        }

        try:
            response = httpx.post(
                "https://api.firecrawl.dev/v1/scrape",
                headers=headers,
                json=payload,
                timeout=self._firecrawl_timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return FetchResult(
                ok=False,
                provider=self.provider_name,
                requested_url=target_url,
                final_url=None,
                status_code=None,
                body=None,
                error_code=FetchFailureCode.NETWORK_ERROR,
                error_detail=str(exc),
                metadata={},
            )

        if response.status_code >= 400:
            return FetchResult(
                ok=False,
                provider=self.provider_name,
                requested_url=target_url,
                final_url=target_url,
                status_code=response.status_code,
                body=None,
                error_code=FetchFailureCode.BLOCKED if response.status_code in {403, 429} else FetchFailureCode.UPSTREAM_ERROR,
                error_detail=self._response_detail(response, "Firecrawl scrape request failed."),
                metadata={},
            )

        payload_json = self._safe_json(response)
        data = payload_json.get("data", {}) if isinstance(payload_json, dict) else {}
        metadata = data.get("metadata", {}) if isinstance(data, dict) else {}

        html_body = data.get("html") if isinstance(data, dict) else None
        markdown_body = data.get("markdown") if isinstance(data, dict) else None
        final_url = metadata.get("sourceURL") or target_url

        return FetchResult(
            ok=True,
            provider=self.provider_name,
            requested_url=target_url,
            final_url=final_url,
            status_code=response.status_code,
            body=html_body or "",
            metadata={
                "firecrawl_markdown": markdown_body or "",
            },
        )

    def _extract_reviews_from_chunks(self, *, target_url: str, chunks: list[str]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        collected: list[dict[str, Any]] = []

        for chunk in chunks[: self._max_chunks]:
            reviews = self._extract_chunk_with_llm(target_url=target_url, chunk=chunk)
            for review in reviews:
                normalized = self._normalize_review(review)
                body_key = (normalized.get("body") or "").strip().lower()
                author_key = (normalized.get("author") or "").strip().lower()
                if not body_key:
                    continue
                dedupe_key = (body_key, author_key)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                collected.append(normalized)

        return collected

    def _extract_chunk_with_llm(self, *, target_url: str, chunk: str) -> list[dict[str, Any]]:
        prompt = (
            "Extract user/customer review records from this markdown chunk. "
            "Return JSON only with this schema: {\"reviews\":[{\"title\":string|null,\"body\":string|null,\"rating\":number|string|null,\"author\":string|null,\"date\":string|null,\"url\":string|null}]}. "
            "Ignore marketing copy and navigation. Include only real review entries."
        )

        if self._llm_provider is None:
            return []

        try:
            generated = self._llm_provider.generate_structured(
                system_prompt="You are a precise data extraction assistant.",
                user_prompt=f"URL: {target_url}\n\nMarkdown chunk:\n{chunk}\n\n{prompt}",
                model=self._llm_model,
                temperature=0.0,
            )
        except LLMProviderError:
            return []

        if not isinstance(generated.payload, dict):
            return []

        reviews = generated.payload.get("reviews")
        if not isinstance(reviews, list):
            return []

        return [item for item in reviews if isinstance(item, dict)]

    def _chunk_markdown(self, markdown: str) -> list[str]:
        text = (markdown or "").strip()
        if not text:
            return []

        size = self._chunk_size_chars
        overlap = min(self._chunk_overlap_chars, max(0, size - 1))
        if overlap >= size:
            overlap = max(0, size // 5)

        chunks: list[str] = []
        start = 0
        while start < len(text) and len(chunks) < self._max_chunks:
            end = min(len(text), start + size)
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = max(0, end - overlap)

        return chunks

    def _normalize_review(self, review: dict[str, Any]) -> dict[str, str | None]:
        body = self._first_text(
            review,
            ["body", "review", "reviewText", "review_text", "text", "content", "comments"],
        )
        return {
            "title": self._first_text(review, ["title", "headline", "summary"]),
            "body": body,
            "rating": self._first_text(review, ["rating", "stars", "score"]),
            "author": self._first_text(review, ["author", "customerName", "reviewer", "name", "user"]),
            "date": self._first_text(review, ["date", "review_date", "reviewDate", "published_at", "publishedAt"]),
            "url": self._first_text(review, ["url", "review_url", "reviewUrl", "link"]),
        }

    def _reviews_to_synthetic_html(self, reviews: list[dict[str, Any]]) -> str:
        cards: list[str] = []
        for idx, review in enumerate(reviews, start=1):
            body = self._safe_text(review.get("body"))
            if not body:
                continue

            title = self._safe_text(review.get("title"))
            author = self._safe_text(review.get("author"))
            date_value = self._safe_text(review.get("date"))
            rating = self._safe_text(review.get("rating"))
            url = self._safe_text(review.get("url"))

            parts = [f"<article data-review-id='gpt-{idx}' class='review-item'>"]
            if title:
                parts.append(f"<h3 class='review-title'>{html.escape(title)}</h3>")
            parts.append(f"<div class='review-body'>{html.escape(body)}</div>")
            if author:
                parts.append(f"<span class='review-author'>{html.escape(author)}</span>")
            if date_value:
                parts.append(f"<time>{html.escape(date_value)}</time>")
            if rating:
                parts.append(
                    f"<span class='review-rating' aria-label='{html.escape(str(rating))} out of 5'>{html.escape(str(rating))}</span>"
                )
            if url:
                parts.append(f"<a href='{html.escape(url)}'>Review URL</a>")
            parts.append("</article>")
            cards.append("".join(parts))

        if not cards:
            return ""

        return "<html><body><section id='gpt-extracted-reviews'>{}</section></body></html>".format("".join(cards))

    def _first_text(self, payload: dict[str, Any], keys: list[str]) -> str | None:
        for key in keys:
            value = payload.get(key)
            text = self._safe_text(value)
            if text:
                return text
        return None

    def _safe_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _response_detail(self, response: httpx.Response, default_message: str) -> str:
        payload = self._safe_json(response)
        if isinstance(payload, dict):
            for key in ["error", "message", "reason"]:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        text = (response.text or "").strip()
        if text:
            return text[:300]

        return default_message

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _config_error(self, target_url: str, detail: str) -> FetchResult:
        return FetchResult(
            ok=False,
            provider=self.provider_name,
            requested_url=target_url,
            final_url=None,
            status_code=None,
            body=None,
            error_code=FetchFailureCode.CONFIG_ERROR,
            error_detail=detail,
            metadata={},
        )
