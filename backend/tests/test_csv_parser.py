"""Tests for CSV review parsing and alias normalization."""

from __future__ import annotations

import pytest

from app.services.ingestion.csv_parser import CSVParseError, CSVParseErrorCode, parse_csv_reviews


def test_csv_parser_alias_mapping_normalizes_rows() -> None:
    csv_content = """Review Text,Stars,Reviewer Name,Headline,Reviewed At,Source URL
Excellent support and workflow improvements,4.5,Sam R,Great product,2026-03-01,https://example.com/r/1
Solid feature set for teams,4,Ana T,Useful,2026-03-02,https://example.com/r/2
"""

    result = parse_csv_reviews(csv_content)

    assert len(result.reviews) == 2
    assert result.column_mapping["body"] == "Review Text"
    assert result.column_mapping["rating"] == "Stars"
    assert result.column_mapping["author"] == "Reviewer Name"
    assert result.column_mapping["title"] == "Headline"
    assert result.column_mapping["date"] == "Reviewed At"
    assert result.column_mapping["url"] == "Source URL"
    assert result.reviews[0]["body"] == "Excellent support and workflow improvements"
    assert result.reviews[0]["rating"] == "4.5"
    assert result.reviews[0]["author"] == "Sam R"


def test_csv_parser_empty_payload_is_typed_error() -> None:
    with pytest.raises(CSVParseError) as exc_info:
        parse_csv_reviews("   ")

    assert exc_info.value.code == CSVParseErrorCode.EMPTY_INPUT


def test_csv_parser_malformed_shape_is_typed_error() -> None:
    malformed = """body,rating,author
Works well,5,Sam,unexpected
"""

    with pytest.raises(CSVParseError) as exc_info:
        parse_csv_reviews(malformed)

    assert exc_info.value.code == CSVParseErrorCode.MALFORMED_CSV


def test_csv_parser_requires_body_alias() -> None:
    missing_body = """rating,author,title,date
5,Sam,Great,2026-03-01
"""

    with pytest.raises(CSVParseError) as exc_info:
        parse_csv_reviews(missing_body)

    assert exc_info.value.code == CSVParseErrorCode.MALFORMED_CSV
