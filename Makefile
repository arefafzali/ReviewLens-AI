SHELL := /bin/sh

.PHONY: dev-up dev-down dev-logs migrate seed test-backend test-frontend test-all

dev-up:
	docker compose up --build

dev-down:
	docker compose down

dev-logs:
	docker compose logs -f --tail=200

migrate:
	docker compose exec backend alembic upgrade head

seed:
	docker compose exec -T db psql -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-reviewlens} < scripts/dev-seed.sql

test-backend:
	docker compose exec backend pytest

test-frontend:
	docker compose exec frontend npm test

test-all: test-backend test-frontend
