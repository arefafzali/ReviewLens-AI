"""Tests for API documentation and OpenAPI schema endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_docs_and_redoc_endpoints_are_available(client: TestClient) -> None:
    docs_response = client.get("/docs")
    redoc_response = client.get("/redoc")

    assert docs_response.status_code == 200
    assert redoc_response.status_code == 200
    assert "swagger" in docs_response.text.lower()
    assert "redoc" in redoc_response.text.lower()


def test_openapi_schema_contains_metadata_and_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()

    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "ReviewLens AI API"
    assert schema["info"]["version"] == "0.1.0"
    assert "review intelligence" in schema["info"]["description"].lower()

    tags = {tag["name"] for tag in schema.get("tags", [])}
    assert "health" in tags
    assert "ingestion" in tags

    assert "/health/live" in schema["paths"]
    assert "/health/ready" in schema["paths"]
    assert "/ingestion/url" in schema["paths"]
    assert "/ingestion/csv" in schema["paths"]

    assert "health" in schema["paths"]["/health/live"]["get"]["tags"]
    assert "ingestion" in schema["paths"]["/ingestion/url"]["post"]["tags"]
