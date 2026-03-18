"""SSRF-safe public URL validation for ingestion fetch pipeline."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_METADATA_HOSTS = {
    "metadata.google.internal",
    "169.254.169.254",
    "100.100.100.200",
}


def validate_public_fetch_url(target_url: str) -> None:
    """Validate URL for safe public fetching.

    Allowed: public http/https targets.
    Rejected: localhost, loopback, private/link-local/reserved IP ranges,
    and metadata service style hosts.
    """

    parsed = urlparse(target_url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed.")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("URL host is required.")

    if host in _METADATA_HOSTS or host.endswith(".internal"):
        raise ValueError("Metadata/internal hosts are not allowed.")

    if host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Localhost targets are not allowed.")

    _validate_host_or_resolved_ips(host)


def _validate_host_or_resolved_ips(host: str) -> None:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None

    if ip is not None:
        _ensure_public_ip(ip)
        return

    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # DNS failure is treated as non-SSRF; fetch layer will return a network error later.
        return

    for info in infos:
        ip_str = info[4][0]
        try:
            resolved_ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        _ensure_public_ip(resolved_ip)


def _ensure_public_ip(ip: ipaddress._BaseAddress) -> None:
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError("Private, loopback, link-local, or reserved addresses are not allowed.")
