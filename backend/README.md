# ReviewLens AI Backend

Minimal FastAPI scaffold for the ReviewLens AI backend.

## Requirements

- Python 3.11+
- Environment variable `REVIEWLENS_ENVIRONMENT` must be set (for example: `local`, `development`, `staging`, `production`, `test`).
- Environment variable `DATABASE_URL` must be set to a Postgres URL for online migrations.
- Environment variable `FIRECRAWL_API_KEY` must be set for URL ingestion fetches.
- Environment variable `OPENAI_API_KEY` must be set for markdown chunk review extraction.

## Install

```bash
pip install -e .[dev]
```

Or run in Docker via monorepo root:

```bash
docker compose up --build
```

## Run locally

```bash
set REVIEWLENS_ENVIRONMENT=local
uvicorn app.main:app --reload
```

With Docker (from monorepo root):

```bash
docker compose up --build backend db
```

## Health checks

- `GET /health/live`
- `GET /health/ready`

## API documentation

- `GET /docs` (Swagger UI)
- `GET /redoc` (ReDoc)
- `GET /openapi.json` (OpenAPI schema)

## Ingestion orchestration APIs

- `POST /ingestion/url`
- `POST /ingestion/csv`

`POST /ingestion/url` supports cache control:

- `reload: false` (default): use cached stored reviews for the same workspace/product/url when available
- `reload: true`: bypass cache and force fresh extraction from source

Both endpoints create an `ingestion_runs` record for each attempt and return a
typed ingestion result contract containing:

- `status`: `success` | `partial` | `failed`
- `outcome_code`: `ok` | `low_data` | `blocked` | `parse_failed` | `invalid_url` | `empty_csv` | `malformed_csv`
- captured review count and timestamps

URL ingestion architecture:

- Firecrawl is the only active fetch provider
- Firecrawl fetches page markdown and HTML
- Markdown is split into overlapping chunks
- Each chunk is sent to GPT for structured review extraction
- Extracted reviews are merged, deduplicated, and used as the ingestion capture result

SSRF-safe validation is applied for URL ingestion fetch targets:

- only `http`/`https`
- rejects localhost, loopback, private/link-local/reserved IPs, and metadata-service style targets

Any public URL can be attempted through Firecrawl + GPT extraction. If no review
content is detected, the run returns `partial` with `low_data` and diagnostics
explaining what was captured.

Optional local tuning:

- `REVIEWLENS_FIRECRAWL_TIMEOUT_SECONDS` controls Firecrawl API timeout.
- `REVIEWLENS_OPENAI_MODEL` selects the extraction model.
- `REVIEWLENS_OPENAI_TIMEOUT_SECONDS` controls extraction request timeout.
- `REVIEWLENS_MARKDOWN_CHUNK_SIZE_CHARS`, `REVIEWLENS_MARKDOWN_CHUNK_OVERLAP_CHARS`, and `REVIEWLENS_MARKDOWN_MAX_CHUNKS` tune chunking behavior.

## Verify Required Sample URLs

Seed local sample workspace/product IDs if needed:

```bash
docker compose exec -T db psql -U postgres -d reviewlens < scripts/dev-seed.sql
```

Then verify required URLs through the ingestion endpoint:

```bash
python scripts/verify_sample_urls.py
```

The script validates:

- https://www.capterra.com/p/164876/PressPage/reviews/
- https://www.amazon.ca/product-reviews/B07SZ9FFT9/ref=cm_cr_dp_d_show_all_btm

## Test

```bash
pytest
```

## Database migrations

Apply migrations:

```bash
set DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/reviewlens
alembic upgrade head
```

Preview migration SQL without applying:

```bash
set DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/reviewlens
alembic upgrade head --sql
```

From Docker container:

```bash
docker compose exec backend alembic upgrade head
```
