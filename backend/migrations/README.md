# Migration Notes

- Alembic scripts live in `migrations/versions`.
- Baseline migration creates the initial Postgres schema for workspaces, products, ingestion runs, reviews, chat sessions, and chat messages.
- `reviews.search_vector` is provisioned for Postgres full-text search indexing in later retrieval work.
- Deduplication support is handled via:
  - partial unique index on source review ID when present
  - unique fingerprint constraint for platform/workspace/product-scoped review content identity
