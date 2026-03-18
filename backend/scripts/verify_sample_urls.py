"""Verify required sample URL ingestion through the live backend API."""

from __future__ import annotations

import json
import os
import sys

import httpx

SAMPLE_URLS = [
    "https://www.capterra.com/p/164876/PressPage/reviews/",
    "https://www.amazon.ca/product-reviews/B07SZ9FFT9/ref=cm_cr_dp_d_show_all_btm",
]


def main() -> int:
    api_base_url = os.getenv("REVIEWLENS_VERIFY_API_BASE_URL", "http://localhost:8000")
    workspace_id = os.getenv("REVIEWLENS_VERIFY_WORKSPACE_ID", "11111111-1111-1111-1111-111111111111")
    product_id = os.getenv("REVIEWLENS_VERIFY_PRODUCT_ID", "22222222-2222-2222-2222-222222222222")

    all_good = True

    for url in SAMPLE_URLS:
        payload = {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "target_url": url,
        }

        response = httpx.post(f"{api_base_url}/ingestion/url", json=payload, timeout=120)
        response.raise_for_status()
        body = response.json()

        print("=" * 80)
        print(url)
        print(json.dumps(body, indent=2))

        usable = body.get("captured_reviews", 0) > 0
        partial_usable = body.get("status") == "partial" and body.get("captured_reviews", 0) > 0
        all_good = all_good and (usable or partial_usable)

    if not all_good:
        print("\nOne or more sample URLs did not produce usable ingestion results.")
        return 1

    print("\nSample URL verification succeeded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
