"""Product-scoped review retrieval using Postgres full-text search ranking."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import datetime
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Review


@dataclass(frozen=True)
class RetrievedReview:
    """Prompt-context ready review retrieval record."""

    review_id: UUID
    title: str | None
    body: str
    rating: float | None
    author_name: str | None
    reviewed_at: date | None
    rank: float
    snippet: str


class ReviewRetrievalService:
    """Retrieves top matching reviews scoped to a single workspace/product."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def retrieve_top_reviews(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        query: str,
        limit: int = 8,
    ) -> list[RetrievedReview]:
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        capped_limit = max(1, min(limit, 20))
        dialect_name = getattr(getattr(self._db, "bind", None), "dialect", None)
        dialect_name = getattr(dialect_name, "name", "")

        if dialect_name == "postgresql":
            return self._retrieve_postgres_fts(
                workspace_id=workspace_id,
                product_id=product_id,
                query=normalized_query,
                limit=capped_limit,
            )

        return self._retrieve_fallback(
            workspace_id=workspace_id,
            product_id=product_id,
            query=normalized_query,
            limit=capped_limit,
        )

    def _retrieve_postgres_fts(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedReview]:
        sql = text(
            """
            SELECT
                r.id,
                r.title,
                r.body,
                r.rating,
                r.author_name,
                r.reviewed_at,
                ts_rank_cd(
                    r.search_vector,
                    websearch_to_tsquery('english', :query)
                ) AS rank,
                LEFT(r.body, 280) AS snippet
            FROM reviews AS r
            WHERE r.workspace_id = :workspace_id
              AND r.product_id = :product_id
              AND r.search_vector @@ websearch_to_tsquery('english', :query)
            ORDER BY rank DESC, r.reviewed_at DESC NULLS LAST, r.created_at DESC
            LIMIT :limit
            """
        )

        rows = self._db.execute(
            sql,
            {
                "workspace_id": workspace_id,
                "product_id": product_id,
                "query": query,
                "limit": limit,
            },
        ).mappings()

        return [
            RetrievedReview(
                review_id=row["id"],
                title=row["title"],
                body=row["body"],
                rating=float(row["rating"]) if row["rating"] is not None else None,
                author_name=row["author_name"],
                reviewed_at=row["reviewed_at"],
                rank=float(row["rank"]),
                snippet=row["snippet"],
            )
            for row in rows
        ]

    def _retrieve_fallback(
        self,
        *,
        workspace_id: UUID,
        product_id: UUID,
        query: str,
        limit: int,
    ) -> list[RetrievedReview]:
        records = (
            self._db.query(Review)
            .filter(
                Review.workspace_id == workspace_id,
                Review.product_id == product_id,
            )
            .all()
        )

        phrase_tokens = _extract_quoted_phrases(query)
        keyword_tokens = _extract_keywords(query)

        scored: list[tuple[float, Review]] = []
        for record in records:
            score = _fallback_score(record=record, phrase_tokens=phrase_tokens, keyword_tokens=keyword_tokens)
            if score <= 0:
                continue
            scored.append((score, record))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].reviewed_at is not None,
                item[1].reviewed_at or date.min,
                item[1].created_at or datetime.min,
            ),
            reverse=True,
        )

        output: list[RetrievedReview] = []
        for score, record in scored[:limit]:
            output.append(
                RetrievedReview(
                    review_id=record.id,
                    title=record.title,
                    body=record.body,
                    rating=float(record.rating) if record.rating is not None else None,
                    author_name=record.author_name,
                    reviewed_at=record.reviewed_at,
                    rank=float(score),
                    snippet=record.body[:280],
                )
            )
        return output


def _extract_quoted_phrases(query: str) -> list[str]:
    return [match.group(1).strip().lower() for match in re.finditer(r'"([^"]+)"', query) if match.group(1).strip()]


def _extract_keywords(query: str) -> list[str]:
    text_without_quotes = re.sub(r'"[^"]+"', " ", query.lower())
    return [token for token in re.findall(r"[a-z0-9]{2,}", text_without_quotes)]


def _fallback_score(*, record: Review, phrase_tokens: list[str], keyword_tokens: list[str]) -> float:
    haystack = " ".join(part for part in [record.title or "", record.body or ""] if part).lower()

    score = 0.0
    for phrase in phrase_tokens:
        if phrase in haystack:
            score += 5.0

    for keyword in keyword_tokens:
        if keyword in haystack:
            score += 1.0

    return score
