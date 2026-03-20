# Backend Test Fixtures

This folder contains deterministic, realistic fixture data used by backend tests.

Goals:
- Avoid live network calls in tests.
- Exercise ingestion, deduplication, analytics, retrieval, and chat flows with representative data.
- Keep fixtures small enough for fast local and CI execution.

Structure:
- `html/`: source-like HTML snapshots from public review pages.
- `markdown/`: markdown payloads similar to Firecrawl scrape output.
- `csv/`: CSV imports that mirror analyst-provided fallback uploads.
- `json/`: extracted review payloads used by fake provider/pipeline tests.

Conventions:
- Keep fixture files stable and human-readable.
- Add comments in tests for why each fixture is chosen.
- Prefer reusing existing fixtures over creating many one-off files.
