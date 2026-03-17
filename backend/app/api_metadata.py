"""Centralized FastAPI metadata and OpenAPI documentation configuration."""

from __future__ import annotations

APP_TITLE = "ReviewLens AI API"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = (
    "Secure review intelligence backend for ORM analysts. "
    "Supports ingestion orchestration for Capterra URL and CSV paths, "
    "plus health and lifecycle APIs."
)

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Service liveness and readiness probes for local and deployment checks.",
    },
    {
        "name": "ingestion",
        "description": "Ingestion orchestration APIs for URL and CSV ingestion attempts.",
    },
]
