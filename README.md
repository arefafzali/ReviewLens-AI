# ReviewLens AI

ReviewLens AI is a web-based Review Intelligence Portal for ORM analysts.

This repository implements the assignment core loop:

1. ingest reviews for a selected entity,
2. inspect ingestion confidence with summary analytics,
3. run guardrailed Q&A over only ingested review evidence.

## Stack

- Backend: FastAPI, SQLAlchemy, Alembic, Postgres
- Frontend: Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui conventions
- Retrieval: Postgres full-text search
- Chat: provider-agnostic LLM abstraction + SSE streaming
- Isolation: anonymous workspace cookies (no authentication)

## Chosen Platform and Rationale

The active review platform is Public review source.

Rationale:

- practical public review URL ingestion,
- predictable review content for extraction/normalization,
- strong fit for assignment-grade ingestion and grounded analysis.

## Core Features

### Ingestion paths

- URL ingestion: `POST /ingestion/url`
  - normal capture path for Public review source review pages,
  - cache reuse for repeated URL ingestions,
  - explicit recapture support via `reload=true`.

- CSV fallback ingestion: `POST /ingestion/csv`
  - fallback path when scraping is incomplete or impractical,
  - alias-aware CSV parsing and typed outcomes.

### Ingestion summary analytics

After ingestion, the UI provides confidence signals:

- captured review count,
- average rating,
- rating histogram,
- review trend over time,
- top recurring keywords,
- suggested starter questions.

### Guardrailed Q&A

- Endpoint: `POST /chat/stream` (SSE: `meta`, `citations`, `token`, `done`, `error`)
- Multi-turn short conversation memory per workspace/product/session
- Prompt-driven scope guard strategy (system prompt first)
- Explicit refusal for out-of-scope asks (other platforms, competitors, world knowledge not in evidence)

### Retrieval approach

- Workspace/product-scoped Postgres FTS retrieval
- Conservative no-hit handling for specific queries to avoid unrelated evidence drift
- Citation payload returned with final streamed response

## Architecture Overview

See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation-aligned architecture details, assumptions, and tradeoffs.

## Setup (Fresh Clone)

1. Copy env templates:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

2. Configure required keys:

- `FIRECRAWL_API_KEY`
- `OPENAI_API_KEY` (when `REVIEWLENS_LLM_PROVIDER=openai`)

3. Start locally:

```bash
docker compose up --build
```

4. Open:

- Frontend: http://localhost:3000
- Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health/live

Backend migrations run automatically on container startup.

## Local Development Flow

With Make:

```bash
make dev-up
make dev-down
make dev-logs
make seed
make test-all
```

Without Make:

```bash
docker compose up --build
docker compose down
docker compose exec -T db psql -U postgres -d reviewlens < scripts/dev-seed.sql
docker compose exec backend pytest
docker compose exec frontend npm test
```

## Quality Checks

Backend:

```bash
docker compose exec backend pytest
```

Frontend:

```bash
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

## Assumptions and Tradeoffs

- No authentication by assignment scope; isolation uses anonymous workspace cookies.
- Scope guard enforcement is prompt-driven, not a heavyweight deterministic policy engine.
- CSV fallback is required for resilience when URL extraction quality is limited.
- Implementation prioritizes a robust core loop over broad product feature breadth.

## Additional Docs

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [backend/README.md](backend/README.md)
- [frontend/README.md](frontend/README.md)


