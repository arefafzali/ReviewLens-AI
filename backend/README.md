# ReviewLens AI Backend

Minimal FastAPI scaffold for the ReviewLens AI backend.

## Requirements

- Python 3.11+
- Environment variable `REVIEWLENS_ENVIRONMENT` must be set (for example: `local`, `development`, `staging`, `production`, `test`).
- Environment variable `DATABASE_URL` must be set to a Postgres URL for online migrations.

## Install

```bash
pip install -e .[dev]
```

Or run in Docker via monorepo root:

```bash
docker compose up --build
```

## Run locally

```bash
set REVIEWLENS_ENVIRONMENT=local
uvicorn app.main:app --reload
```

With Docker (from monorepo root):

```bash
docker compose up --build backend db
```

## Health checks

- `GET /health/live`
- `GET /health/ready`

## API documentation

- `GET /docs` (Swagger UI)
- `GET /redoc` (ReDoc)
- `GET /openapi.json` (OpenAPI schema)

## Ingestion orchestration APIs

- `POST /ingestion/url`
- `POST /ingestion/csv`

Both endpoints create an `ingestion_runs` record for each attempt and return a
typed ingestion result contract containing:

- `status`: `success` | `partial` | `failed`
- `outcome_code`: `ok` | `low_data` | `blocked` | `parse_failed` | `invalid_url` | `empty_csv` | `malformed_csv`
- captured review count and timestamps

## Test

```bash
pytest
```

## Database migrations

Apply migrations:

```bash
set DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/reviewlens
alembic upgrade head
```

Preview migration SQL without applying:

```bash
set DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/reviewlens
alembic upgrade head --sql
```

From Docker container:

```bash
docker compose exec backend alembic upgrade head
```
