# Job Intelligence Platform

Discovers job postings directly from company career infrastructure and ATS platforms, normalizes them into a unified schema, and makes them searchable. See [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) for the full product spec and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for what's actually built so far.

This repo currently implements the first two vertical slices:

1. **Greenhouse end-to-end** — source registration, job sync, normalization, Level-1 deduplication.
2. **Search UI** (Phase 4) — Next.js frontend with keyword/location/company/freshness search, job cards, and a job detail view backed by an extended `GET /jobs` endpoint.

No other providers, no matching, no application tracking yet.

## Local development

### 1. Start infrastructure

```bash
cp .env.example .env
docker compose up -d postgres redis
```

### 2. Run database migrations

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
```

(Or from a container: `docker compose run --rm api alembic upgrade head`.)

### 3. Run the full stack

```bash
docker compose up
```

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000 (interactive docs at `/docs`)
- **Worker**: consumes the `sync` queue via Redis

### 4. Try it

```bash
# Register a Greenhouse board (use a real public board URL)
curl -X POST localhost:8000/sources -H 'content-type: application/json' \
  -d '{"url": "https://boards.greenhouse.io/<board-token>"}'

# Trigger a sync (returns a Celery task id)
curl -X POST localhost:8000/sources/1/sync

# List jobs once the sync completes
curl "localhost:8000/jobs?source_id=1"
```

## Tests

Tests run against a real Postgres database (the integration test exercises the full sync pipeline end-to-end). `conftest.py` creates the `job_intelligence_test` database and tables automatically, and wraps each test in a transaction that's rolled back afterward.

```bash
docker compose up -d postgres
cd backend
pip install -e ".[dev]"
pytest ../tests
```

## Repository layout

```
backend/app/        FastAPI app: domain models, providers, discovery, normalization,
                     deduplication, sync pipeline, API routes
frontend/            Next.js + TypeScript search UI (App Router)
workers/             Celery app + tasks (wraps backend/app/sync)
infrastructure/      Dockerfiles
tests/               unit + integration tests
docs/                product spec + architecture notes
```
