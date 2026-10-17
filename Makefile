# ScentVault dev tasks (macOS/Linux/WSL/Git Bash). On Windows PowerShell use ./tasks.ps1 <target>.
API := apps/api
PY  := $(API)/.venv/bin/python
ifeq ($(OS),Windows_NT)
PY  := $(API)/.venv/Scripts/python.exe
endif

.PHONY: help setup up down migrate seed demo api worker admin mobile types test lint check

help:            ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

setup:           ## create the API venv and install everything
	cd $(API) && python -m venv .venv && .venv/bin/pip install -e ".[dev,ml]"
	cd apps/admin && npm ci
	cd apps/mobile && npm ci

up:              ## start Postgres + Redis
	docker compose up -d db redis

down:            ## stop containers
	docker compose down

migrate:         ## apply database migrations
	cd $(API) && ../../$(PY) -m alembic upgrade head

seed:            ## reference data (brands, notes, families, accords, occasions, retailers)
	cd $(API) && ../../$(PY) -m seeds.run

demo:            ## reference data + ~24 demo fragrances
	cd $(API) && ../../$(PY) -m seeds.run --demo

api:             ## API on :8004 with reload
	cd $(API) && ../../$(PY) -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8004

worker:          ## background worker (embeddings, alerts, nudges)
	cd $(API) && ../../$(PY) -m arq app.workers.arq_worker.WorkerSettings

admin:           ## admin panel on :5173
	cd apps/admin && npm run dev

mobile:          ## Expo dev server (set EXPO_PUBLIC_API_URL in apps/mobile/.env)
	cd apps/mobile && npx expo start

types:           ## regenerate packages/api-types from the API schema
	cd $(API) && ../../$(PY) -m scripts.gen_types

test:            ## API tests (needs Postgres; see TEST_DATABASE_URL in README)
	cd $(API) && ../../$(PY) -m pytest -q

lint:            ## ruff + mypy + TypeScript checks
	cd $(API) && ../../$(PY) -m ruff check . && ../../$(PY) -m mypy app scripts
	cd apps/admin && npx tsc -b && npx eslint .
	cd apps/mobile && npx tsc --noEmit

check: lint test ## everything CI runs
	cd $(API) && ../../$(PY) -m scripts.gen_types --check
