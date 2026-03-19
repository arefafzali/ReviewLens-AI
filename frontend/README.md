# ReviewLens AI Frontend

Initial frontend scaffold using Next.js 14 App Router, TypeScript, Tailwind CSS, and shadcn/ui conventions.

## Current page scope

The root page now provides a minimal analyst workspace surface for the core loop:

- ingestion panel section with two entry paths:
	- A URL input with validation and backend submission to `/ingestion/url`
	- CSV upload with backend submission to `/ingestion/csv`
	- Frontend first calls `/context/ensure` to guarantee workspace/product IDs exist before ingestion
- ingestion summary section updates after successful URL or CSV ingestion without page reload
	- renders capture stats, rating histogram, review trend, and top recurring keywords from backend analytics
	- handles sparse datasets with explicit low-signal guidance
- suggested questions section now renders backend-provided `summary_snapshot.suggested_questions`
	- displays up to 5 grounded starter prompts
	- clicking a suggestion seeds/submits an analyst chat question
	- once chat starts, the suggestions section reduces to top suggestion with an option to expand
	- handles no-suggestion backend responses with a graceful empty state
- chat section now includes a lightweight analyst conversation panel for seeded/submitted questions
	- modular transcript + composer layout with user and assistant message roles
	- consumes backend `/chat/stream` SSE events (`meta`, `citations`, `token`, `done`, `error`)
	- renders assistant tokens incrementally during streaming and supports cancel/abort
	- final assistant message settles from structured `done` payload classification and answer text

When URL ingestion is blocked or low-confidence, the ingestion panel provides inline CSV fallback guidance.

Optional local context overrides for ingestion payload IDs:

- `NEXT_PUBLIC_REVIEWLENS_WORKSPACE_ID`
- `NEXT_PUBLIC_REVIEWLENS_PRODUCT_ID`
- `NEXT_PUBLIC_INGESTION_TIMEOUT_MS` (milliseconds for ingestion requests, `0` disables client timeout and allows multi-minute runs)

## Run locally

```bash
npm install
npm run dev
```

Open http://localhost:3000.

Run with Docker from monorepo root:

```bash
docker compose up --build frontend backend db
```

## Test

```bash
npm test
```

Run tests from Docker container:

```bash
docker compose exec frontend npm test
```
