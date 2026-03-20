"""Tests for SSRF-safe public URL validation behavior."""

from __future__ import annotations

import pytest

from app.services.ingestion.url_safety import validate_public_fetch_url


@pytest.mark.parametrize(
    "url",
    [
        "https://www.reviews.example.com/p/164876/PressPage/reviews/",
        "http://example.org/reviews",
    ],
)
def test_public_http_urls_are_allowed(monkeypatch, url: str) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    validate_public_fetch_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://localhost:8000/",
        "https://127.0.0.1/test",
        "https://169.254.169.254/latest/meta-data/",
    ],
)
def test_disallowed_urls_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_public_fetch_url(url)


def test_domain_resolving_to_private_ip_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.ingestion.url_safety.socket.getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("10.0.0.2", 0))],
    )

    with pytest.raises(ValueError):
        validate_public_fetch_url("https://public-looking-host.example/path")

