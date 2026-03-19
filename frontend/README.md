# ReviewLens AI Frontend

Initial frontend scaffold using Next.js 14 App Router, TypeScript, Tailwind CSS, and shadcn/ui conventions.

## Current page scope

The root page now provides a minimal analyst workspace surface for the core loop:

- ingestion panel section with two entry paths:
	- A URL input with validation
	- CSV upload with file validation
- ingestion summary section (capture confidence placeholder)
- suggested questions section (grounded starter prompts placeholder)
- chat section (guardrailed Q&A placeholder)

Each section includes a loading state so backend integration can be added incrementally without changing layout structure.

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
