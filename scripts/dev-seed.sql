-- Minimal seed data for local verification of schema wiring.
-- Idempotent inserts use fixed UUIDs and ON CONFLICT clauses.

INSERT INTO workspaces (id, name)
VALUES ('11111111-1111-1111-1111-111111111111', 'Local Workspace')
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = now();

INSERT INTO products (id, workspace_id, platform, name, source_url)
VALUES (
  '22222222-2222-2222-2222-222222222222',
  '11111111-1111-1111-1111-111111111111',
  'capterra',
  'Local Seed Product',
  'https://www.capterra.com/p/seed-product'
)
ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, updated_at = now();

INSERT INTO ingestion_runs (id, workspace_id, product_id, source_type, status, target_url, started_at, completed_at)
VALUES (
  '33333333-3333-3333-3333-333333333333',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  'scrape',
  'success',
  'https://www.capterra.com/p/seed-product/reviews',
  now(),
  now()
)
ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, updated_at = now();

INSERT INTO reviews (
  id,
  workspace_id,
  product_id,
  ingestion_run_id,
  source_platform,
  source_review_id,
  review_fingerprint,
  title,
  body,
  rating,
  reviewed_at,
  author_name,
  language_code
)
VALUES (
  '44444444-4444-4444-4444-444444444444',
  '11111111-1111-1111-1111-111111111111',
  '22222222-2222-2222-2222-222222222222',
  '33333333-3333-3333-3333-333333333333',
  'capterra',
  'seed-review-1',
  'seed-fingerprint-1',
  'Great support and reporting',
  'The platform helped us improve response quality and reporting visibility.',
  4.5,
  CURRENT_DATE,
  'Seed Analyst',
  'en'
)
ON CONFLICT (workspace_id, product_id, source_platform, review_fingerprint)
DO UPDATE SET body = EXCLUDED.body, updated_at = now();
