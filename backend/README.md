# ReviewLens AI Backend

Minimal FastAPI scaffold for the ReviewLens AI backend.

## Requirements

- Python 3.11+
- Environment variable `REVIEWLENS_ENVIRONMENT` must be set (for example: `local`, `development`, `staging`, `production`, `test`).

## Install

```bash
pip install -e .[dev]
```

## Run locally

```bash
set REVIEWLENS_ENVIRONMENT=local
uvicorn app.main:app --reload
```

## Health checks

- `GET /health/live`
- `GET /health/ready`

## Test

```bash
pytest
```
