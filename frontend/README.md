# ReviewLens AI Frontend

Initial frontend scaffold using Next.js 14 App Router, TypeScript, Tailwind CSS, and shadcn/ui conventions.

## Current page scope

The root page now provides a minimal analyst workspace surface for the core loop:

- ingestion panel section with two entry paths:
	- A URL input with validation and backend submission to `/ingestion/url`
	- CSV upload with backend submission to `/ingestion/csv`
	- Frontend first calls `/context/ensure` to guarantee workspace/product IDs exist before ingestion
	- URL and CSV both create/select product-scoped context before ingestion, so each source is analyzed independently
	- CSV requests send `source_ref` + `csv_content` and are persisted through the same ingestion source-reference field as URL runs
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
	- classification-specific rendering distinguishes `answer`, `out_of_scope`, and `insufficient_evidence`
	- refusal/evidence-limited outcomes explicitly reinforce grounding to ingested reviews only
	- assistant answers render compact supporting citation snippets from backend evidence payloads
	- citation cards include available review metadata (evidence id, title, author, date, rating) when present
	- recent persisted conversation history is hydrated on workspace re-entry/page refresh
	- active chat session id is persisted per workspace/product to keep follow-up turns coherent

Reusable dashboard components:

- `ProductCard` (`src/components/dashboard/product-card.tsx`) provides a typed, reusable product summary card
- Displays name, platform/source badge, review count, average rating, latest capture time, analyze CTA, and optional delete-action slot
- Handles partial/missing product fields with safe fallback labels

Product selection behavior:

- The workspace renders a product selector list and scopes summary/chat/history to the selected product only
- URL sources map to stable product IDs via normalized URL keys
- CSV sources map to stable product IDs via generated CSV source fingerprints
- Successful ingestion optimistically prepends/updates the product card immediately without requiring a full dashboard reload
- Product deletion is optimistic with automatic rollback and error feedback if the API call fails

Dedicated product detail route:

- `GET /product/[id]` renders a focused analysis shell for one product entity
- Reuses existing analysis sections: ingestion summary, suggested questions, and scoped analyst chat
- Invalid route IDs render a clean not-found state without breaking the app shell

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
