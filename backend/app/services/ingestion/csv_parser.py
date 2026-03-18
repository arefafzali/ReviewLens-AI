"""CSV parsing and normalization for ingestion fallback mode."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from io import StringIO


class CSVParseErrorCode(str, Enum):
    EMPTY_INPUT = "empty_input"
    MALFORMED_CSV = "malformed_csv"


class CSVParseError(ValueError):
    """Raised when CSV content cannot be parsed into normalized review rows."""

    def __init__(self, code: CSVParseErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class CSVParseResult:
    """Normalized CSV parse output for downstream persistence."""

    reviews: list[dict[str, str | None]]
    column_mapping: dict[str, str]


_ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "body": ("body", "review", "reviewtext", "review_text", "text", "content", "comment", "comments", "feedback"),
    "rating": ("rating", "stars", "score", "overallrating", "overallscore"),
    "author": ("author", "reviewer", "reviewername", "name", "username", "user", "customer", "reviewedby"),
    "title": ("title", "headline", "summary", "subject"),
    "date": ("date", "reviewdate", "reviewedat", "publishedat", "createdat"),
    "url": ("url", "reviewurl", "link", "sourceurl"),
}


def parse_csv_reviews(csv_content: str) -> CSVParseResult:
    """Parse CSV review file and normalize rows to scraper-equivalent fields.

    Output schema per review row:
    - title
    - body
    - rating
    - author
    - date
    - url
    """

    if not csv_content.strip():
        raise CSVParseError(CSVParseErrorCode.EMPTY_INPUT, "Empty CSV payload.")

    stream = StringIO(csv_content)
    try:
        reader = csv.DictReader(stream, restkey="__extra_fields__")
    except csv.Error as exc:
        raise CSVParseError(CSVParseErrorCode.MALFORMED_CSV, str(exc)) from exc

    headers = list(reader.fieldnames or [])
    if not headers:
        raise CSVParseError(CSVParseErrorCode.MALFORMED_CSV, "Missing header row.")

    header_lookup = {_normalize_header(name): name for name in headers if _normalize_header(name)}
    column_mapping = _resolve_alias_mapping(header_lookup)
    if "body" not in column_mapping:
        raise CSVParseError(CSVParseErrorCode.MALFORMED_CSV, "CSV must include a body/review text column.")

    reviews: list[dict[str, str | None]] = []
    try:
        for row in reader:
            if row is None:
                continue

            if row.get("__extra_fields__"):
                raise CSVParseError(
                    CSVParseErrorCode.MALFORMED_CSV,
                    "CSV rows are inconsistent with header shape.",
                )

            normalized = {
                "title": _extract_value(row, column_mapping.get("title")),
                "body": _extract_value(row, column_mapping.get("body")),
                "rating": _extract_value(row, column_mapping.get("rating")),
                "author": _extract_value(row, column_mapping.get("author")),
                "date": _extract_value(row, column_mapping.get("date")),
                "url": _extract_value(row, column_mapping.get("url")),
            }

            if not normalized["body"]:
                continue

            reviews.append(normalized)
    except csv.Error as exc:
        raise CSVParseError(CSVParseErrorCode.MALFORMED_CSV, str(exc)) from exc

    return CSVParseResult(reviews=reviews, column_mapping=column_mapping)


def _resolve_alias_mapping(header_lookup: dict[str, str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical_field, aliases in _ALIAS_GROUPS.items():
        for alias in aliases:
            if alias in header_lookup:
                mapping[canonical_field] = header_lookup[alias]
                break
    return mapping


def _normalize_header(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch == "_")


def _extract_value(row: dict[str, object], column_name: str | None) -> str | None:
    if not column_name:
        return None
    raw = row.get(column_name)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None
