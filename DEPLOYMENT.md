# Deployment Guide

This guide documents a free-tier-friendly deployment path for ReviewLens AI.

## Recommended Hosting Shape

- Frontend: Vercel (free tier)
- Backend API: Render, Railway, or Fly.io (free tier where available)
- Postgres: Neon or Supabase Postgres (free tier)

This split is practical for public URL access and does not require custom infrastructure code.

## Health Checks

Backend health endpoints:

- Live: `/health/live`
- Ready: `/health/ready`

Suggested platform health check path: `/health/live`

## Required Environment Variables

## Backend

Required:

- `REVIEWLENS_ENVIRONMENT=production`
- `DATABASE_URL=<managed-postgres-url>`
- `FIRECRAWL_API_KEY=<secret>`
- `OPENAI_API_KEY=<secret>`
- `REVIEWLENS_LLM_PROVIDER=openai`
- `REVIEWLENS_CORS_ALLOW_ORIGINS=<frontend-origin>`

Recommended production cookie/cors settings:

- `REVIEWLENS_WORKSPACE_COOKIE_SECURE=true`
- `REVIEWLENS_WORKSPACE_COOKIE_HTTP_ONLY=true`
- `REVIEWLENS_WORKSPACE_COOKIE_SAME_SITE=none` (for cross-site frontend/backend)
- `REVIEWLENS_WORKSPACE_COOKIE_PATH=/`

Notes:

- `REVIEWLENS_CORS_ALLOW_ORIGINS` is comma-separated (for example: `https://your-app.vercel.app`).
- Do not use `*` in production.
- The backend enforces production cookie/CORS guardrails at startup.

## Frontend

Required:

- `NEXT_PUBLIC_API_BASE_URL=https://<your-backend-domain>`

Optional:

- `NEXT_PUBLIC_INGESTION_TIMEOUT_MS=0`

Do not set workspace/product override env vars in production:

- `NEXT_PUBLIC_REVIEWLENS_WORKSPACE_ID`
- `NEXT_PUBLIC_REVIEWLENS_PRODUCT_ID`

## Deployment Steps

1. Provision managed Postgres (Neon/Supabase).
2. Deploy backend service using `backend/Dockerfile.prod`.
3. Set backend env vars (including CORS + cookie settings).
4. Run migrations on deploy startup (`alembic upgrade head`).
5. Verify backend health at `/health/live` and `/docs`.
6. Deploy frontend (Vercel or container) with `NEXT_PUBLIC_API_BASE_URL` pointing to backend.
7. Validate end-to-end flow:
   - URL ingestion
   - CSV fallback ingestion
   - CSV sample import from `samples/reviews_sample.csv`
   - summary analytics
   - guardrailed chat + refusal behavior

## Container-Based Production Option

This repo includes:

- `backend/Dockerfile.prod`
- `frontend/Dockerfile.prod`
- `docker-compose.prod.yml`

Use this path for low-cost VM/container hosting when platform-native services are not used.

## Security and Operational Notes

- Never commit secrets to git.
- Prefer platform secret managers for API keys and DB credentials.
- Keep backend and frontend on HTTPS in production.
- Use separate environments for staging and production.
- Review logs for ingestion failures and chat stream errors.

Quick CSV ingestion test payload (example):

```json
{
  "source_ref": "https://example.com/imports/reviews_sample.csv",
  "csv_content": "<paste samples/reviews_sample.csv content>"
}
```
