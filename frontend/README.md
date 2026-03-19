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
- suggested questions section (grounded starter prompts placeholder)
- chat section (guardrailed Q&A placeholder)

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
