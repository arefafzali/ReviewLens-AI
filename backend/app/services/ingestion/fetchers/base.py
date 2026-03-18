"""Generic fetch provider abstractions for public URL ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol


class FetchFailureCode(str, Enum):
    BLOCKED = "blocked"
    UPSTREAM_ERROR = "upstream_error"
    NETWORK_ERROR = "network_error"
    CONFIG_ERROR = "config_error"


@dataclass(frozen=True)
class FetchResult:
    """Normalized output from a public URL fetch attempt."""

    ok: bool
    provider: str
    requested_url: str
    final_url: str | None
    status_code: int | None
    body: str | None
    error_code: FetchFailureCode | None = None
    error_detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PublicUrlFetcher(Protocol):
    """Fetcher contract for retrieving public URL HTML content."""

    provider_name: str

    def fetch(self, target_url: str) -> FetchResult:
        """Fetch target URL and return normalized fetch result."""
