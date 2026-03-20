# ReviewLens AI Monorepo

Local-first monorepo scaffold for ReviewLens AI with:

- backend: FastAPI + Alembic + Postgres schema baseline
- frontend: Next.js 14 App Router + TypeScript + Tailwind + shadcn/ui conventions
- db: Postgres 16

## Quick Start (Fresh Clone)

1. Copy environment examples:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

2. Start local stack:

```bash
docker compose up --build
```

3. Open apps:

- Frontend: http://localhost:3000
- Backend health: http://localhost:8000/health/live

Backend container runs migrations on startup using Alembic.

## Common Dev Commands

If you have Make installed:

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

## Notes

- `scripts/dev-seed.sql` inserts one workspace, one product, one ingestion run, and one review for quick local verification.
- Frontend points to backend using `NEXT_PUBLIC_API_BASE_URL`.

Release hygiene tip:

- Before committing focused work, verify staged file scope:

```powershell
pwsh ./scripts/check-staged-files.ps1 -AllowedPrefixes backend/,frontend/
```

You can narrow prefixes for a task-specific commit, for example:

```powershell
pwsh ./scripts/check-staged-files.ps1 -AllowedPrefixes frontend/src/components/workspace/
```
