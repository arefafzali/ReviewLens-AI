# ReviewLens AI Backend

Minimal FastAPI scaffold for the ReviewLens AI backend.

## Requirements

- Python 3.11+
- Environment variable `REVIEWLENS_ENVIRONMENT` must be set (for example: `local`, `development`, `staging`, `production`, `test`).
- Environment variable `DATABASE_URL` must be set to a Postgres URL for online migrations.
- Environment variable `FIRECRAWL_API_KEY` must be set for URL ingestion fetches.
- Environment variable `OPENAI_API_KEY` must be set when `REVIEWLENS_LLM_PROVIDER=openai`.

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

- `POST /context/ensure`
- `POST /ingestion/url`
- `POST /ingestion/csv`
- `POST /chat/stream` (SSE)

## Product persistence APIs

- `GET /products?workspace_id=<uuid>`
- `GET /products/{id}?workspace_id=<uuid>`
- `DELETE /products/{id}?workspace_id=<uuid>`

Product APIs are workspace-aware and return summary fields suitable for dashboard/list
and product detail pages, including:

- `total_reviews`
- `average_rating`
- `chat_session_count`
- latest ingestion status snapshot

Delete semantics are productized for portal cleanup: deleting a product removes dependent
reviews, chat sessions/messages, and ingestion runs for that workspace/product context.

`POST /context/ensure` is an idempotent bootstrap endpoint used by the frontend
to ensure `workspace_id` and `product_id` records exist before ingestion calls.
This prevents foreign-key failures when browser-local IDs are first seen by the backend.

`POST /ingestion/url` supports cache control:

- `reload: false` (default): use cached stored reviews for the same workspace/product/url when available
- `reload: true`: bypass cache and force fresh extraction from source

`POST /ingestion/csv` supports flexible column aliases. Required field:

- body aliases: `body`, `review`, `review_text`, `reviewText`, `text`, `content`, `comment`, `comments`, `feedback`

Optional aliases:

- rating aliases: `rating`, `stars`, `score`, `overallRating`, `overallScore`
- author aliases: `author`, `reviewer`, `name`, `username`, `user`, `customer`
- title aliases: `title`, `headline`, `summary`, `subject`
- date aliases: `date`, `reviewDate`, `reviewedAt`, `publishedAt`, `createdAt`

CSV rows are normalized to the same downstream review shape as URL ingestion:

- `title`, `body`, `rating`, `author`, `date`, `url`

URL and CSV attempts now share one source reference storage path in `ingestion_runs.target_url`.
The only discriminator between sources is `source_type` (`scrape` or `csv_upload`).

`POST /ingestion/csv` request includes:

- `source_ref`: stable source identifier for the CSV import (frontend generates and reuses this per CSV source)
- `csv_content`: raw CSV data

Both endpoints create an `ingestion_runs` record for each attempt and return a
typed ingestion result contract containing:

- `status`: `success` | `partial` | `failed`
- `outcome_code`: `ok` | `low_data` | `blocked` | `parse_failed` | `invalid_url` | `empty_csv` | `malformed_csv`
- captured review count and timestamps

For successful URL/CSV ingestions, diagnostics include normalization and dedupe counters:

- `persisted_reviews`: newly inserted rows
- `duplicates_removed`: rows removed by deterministic deduplication
- `skipped_missing_body`: rows dropped because required review text was missing

Successful ingestions also compute and persist grounded starter questions to support
guardrailed follow-up analysis:

- `products.stats.suggested_questions`: product-level starter questions based on stored reviews
- `ingestion_runs.summary_snapshot.suggested_questions`: run-level starter questions for the latest ingestion batch

URL ingestion architecture:

- Firecrawl is the only active fetch provider
- Firecrawl fetches page markdown and HTML
- Markdown is split into overlapping chunks
- Each chunk is sent through the provider-agnostic LLM interface for structured review extraction
- Extracted reviews are merged, deduplicated, and used as the ingestion capture result

LLM provider architecture:

- `app/llm/base.py` defines a common contract for chat, structured generation, and streaming chunks
- `app/llm/factory.py` selects provider adapters via `REVIEWLENS_LLM_PROVIDER`
- `app/llm/openai_provider.py` is the production adapter for OpenAI chat completions
- `app/llm/fake_provider.py` is a deterministic adapter for tests and local simulation

Guardrailed Q&A prompt architecture:

- `app/services/chat/prompt_builder.py` builds deterministic system/user prompts from product identity, ingestion context, and retrieved review evidence
- The system prompt contains explicit scope guard, refusal behavior, and insufficient-evidence behavior
- Scope enforcement is prompt-first (assignment requirement), without a heavyweight deterministic policy engine

Conversation memory architecture:

- `app/repositories/chat_memory.py` persists chat sessions and messages scoped to workspace/product
- `app/services/chat/conversation_memory.py` provides session lookup/creation and bounded history loading
- Recent context window is capped to the last 6 turns (12 messages) to keep prompts bounded

Streaming chat contract:

- Endpoint: `POST /chat/stream`
- Request: `workspace_id`, `product_id`, `question`, optional `chat_session_id`
- Server workflow per request:
	1. load recent bounded conversation history
	2. retrieve product-scoped review evidence
	3. build scope-guarded prompt
	4. stream model output tokens
- SSE events emitted:
	- `meta`: session/provider/context metadata
	- `citations`: machine-readable evidence payload
	- `token`: incremental answer text deltas
	- `done`: final answer with normalized classification and citations
	- `error`: structured stream error payload
- Final classification values:
	- `answer`
	- `out_of_scope`
	- `insufficient_evidence`

SSRF-safe validation is applied for URL ingestion fetch targets:

- only `http`/`https`
- rejects localhost, loopback, private/link-local/reserved IPs, and metadata-service style targets

Any public URL can be attempted through Firecrawl + GPT extraction. If no review
content is detected, the run returns `partial` with `low_data` and diagnostics
explaining what was captured.

Optional local tuning:

- `REVIEWLENS_FIRECRAWL_TIMEOUT_SECONDS` controls Firecrawl API timeout.
- `REVIEWLENS_LLM_PROVIDER` selects `openai` or `fake` provider adapter.
- `REVIEWLENS_LLM_FAKE_STRUCTURED_RESPONSE` supplies deterministic JSON payload for fake provider tests.
- `REVIEWLENS_OPENAI_MODEL` selects the extraction model.
- `REVIEWLENS_OPENAI_TIMEOUT_SECONDS` controls extraction request timeout.
- `REVIEWLENS_MARKDOWN_CHUNK_SIZE_CHARS`, `REVIEWLENS_MARKDOWN_CHUNK_OVERLAP_CHARS`, and `REVIEWLENS_MARKDOWN_MAX_CHUNKS` tune chunking behavior.
- `REVIEWLENS_CORS_ALLOW_ORIGINS` configures allowed browser origins for API access (comma-separated, e.g. `http://localhost:3000,http://127.0.0.1:3000`).

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
