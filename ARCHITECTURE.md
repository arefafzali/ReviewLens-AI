# ReviewLens AI Architecture

## Purpose

ReviewLens AI supports one analyst workflow:

1. ingest reviews for a selected entity,
2. inspect ingestion confidence through summary analytics,
3. run guardrailed Q&A over ingested review evidence.

## System Components

### Frontend

Next.js App Router + TypeScript frontend responsible for:

- URL/CSV ingestion entry,
- product context switching,
- ingestion summary rendering,
- SSE chat streaming and citation display.

### Backend

FastAPI backend responsible for:

- workspace/product context bootstrapping,
- ingestion orchestration (URL + CSV),
- persistence and analytics snapshots,
- retrieval and guardrailed prompt construction,
- SSE chat streaming and chat memory persistence.

### Database

Postgres stores:

- workspaces,
- products,
- ingestion runs,
- normalized reviews,
- chat sessions/messages.

Postgres full-text search powers retrieval.

## Chosen Platform

Public review source is the selected public review platform.

Rationale:

- practical URL ingestion path,
- predictable review data for extraction/normalization,
- assignment-aligned coverage for ingestion -> summary -> Q&A.

## Ingestion Design

### URL ingestion

- Endpoint: `POST /ingestion/url`
- Path: fetch -> extract -> normalize -> dedupe -> persist -> summarize
- Supports cache reuse and recapture (`reload=true`).

### CSV fallback ingestion

- Endpoint: `POST /ingestion/csv`
- Accepts `source_ref` + `csv_content`
- Alias-aware parsing and typed error/outcome modeling

Both ingestion paths converge into the same persistence and analytics pipeline.

## Summary Analytics

The ingestion summary provides confidence indicators:

- captured reviews,
- average rating,
- rating histogram,
- review trend over time,
- recurring keywords,
- suggested starter questions.

## Guardrailed Q&A Strategy

### Prompt-first scope guard

Scope enforcement is driven primarily by system prompt instructions.

Allowed scope:

- analysis of ingested reviews for selected product/platform.

Refused scope:

- competitors,
- other platforms,
- world knowledge not present in ingested evidence.

### Retrieval grounding

- retrieval is workspace/product scoped,
- prompt includes ingestion context + retrieved evidence,
- streamed response includes citation payload,
- specific no-hit query handling is conservative to avoid unrelated fallback evidence.

## Streaming and Memory

Chat endpoint: `POST /chat/stream`

SSE events:

- `meta`
- `citations`
- `token`
- `done`
- `error`

Classification outcomes:

- `answer`
- `out_of_scope`
- `insufficient_evidence`

Short multi-turn memory is persisted per workspace/product/session.

## Workspace Isolation

No user authentication is implemented by design.

Isolation model:

- anonymous workspace cookie,
- optional workspace_id override,
- all product/ingestion/chat data scoped to workspace.

## Assumptions

- analysts are trusted internal users,
- selected product context constrains all analysis,
- assignment scope prioritizes core loop reliability.

## Tradeoffs

- Prompt-first guardrails are assignment-aligned but less deterministic than policy-engine enforcement.
- Cookie-scoped anonymous workspaces avoid auth complexity but are not identity security.
- CSV fallback improves reliability when URL extraction is incomplete.

## Reviewer Checklist

A reviewer can:

1. run `docker compose up --build`,
2. ingest Public review source URL or CSV fallback,
3. inspect summary analytics,
4. ask in-scope and out-of-scope questions,
5. verify refusal behavior and citations,
6. inspect OpenAPI docs at `/docs`.

