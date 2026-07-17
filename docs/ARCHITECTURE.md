# Architecture — Current State

This tracks what has actually been built against the phases in [PRODUCT_SPEC.md](./PRODUCT_SPEC.md#31-recommended-development-phases).

## Built (Phase 0–4)

### Phase 0–3: Greenhouse end-to-end

- **Data model**: `Company`, `JobSource`, `Job` (spec §7.4–7.6, trimmed — see below). SQLAlchemy models in `backend/app/domain/models.py`, one Alembic migration.
- **Provider framework**: `JobProvider` ABC (spec §8) in `backend/app/providers/base.py`. `GreenhouseProvider` implemented against Greenhouse's public boards-api (no scraping, no browser automation — spec §4 Principle 1 / §35).
- **Discovery**: Mode D only (spec §11) — user pastes a Greenhouse board URL, `backend/app/discovery/source_detection.py` detects the provider and extracts the board token. Mode A/B/C (company-name search, CSV import, search-engine discovery) are not built.
- **Sync pipeline**: `backend/app/sync/sync_service.py` — fetch → normalize → content-hash → upsert (Level-1 dedupe only, spec §15) → mark disappeared jobs `closed` → update `JobSource` sync status/error, with a structured summary log line (spec §33).
- **Background processing**: Celery task in `workers/tasks.py` wraps `sync_service.sync_source`; triggered via the API, matching the API → Queue → Worker → DB flow in spec §6.
- **API**: `POST /sources`, `POST /sources/{id}/sync`, `GET /jobs` (list + basic filters/pagination, sorted by freshness per spec §16/§18).
- **Reliability**: Greenhouse HTTP client retries 429/5xx/timeouts with the backoff schedule from spec §34.
- **Tests**: unit tests for source detection, normalization, content hashing; an integration test running the sync pipeline twice against Postgres to verify add/update/close transitions (spec §32).

### Phase 4: Search UI

- **Search API** — `GET /jobs` now supports `q` (ILIKE keyword search across title/description/company name), `location` (ILIKE substring), `company_id`, `posted_since_days` (freshness filter, spec §18), `status`, and pagination — sorted by `first_seen_at desc`. `GET /jobs/{id}` returns a single job with `company_name` joined in. `GET /companies` returns companies with active-job counts (backs the filter dropdown).
- **Frontend** — Next.js 15 (App Router) + TypeScript + Tailwind in `frontend/`:
  - Search page with search bar, location/company/freshness filters, job cards showing "First seen X ago" freshness badges. URL query params are the source of truth so state is shareable.
  - Job detail page with metadata grid and full formatted description, plus a canonical "Apply on company site ↗" CTA that preserves the employer's own application URL (spec §35).
- **CORS** middleware on the API allows `localhost:3000` for local dev.
- **`docker compose up`** now brings up `postgres`, `redis`, `api`, `worker`, and `frontend` together.

### Search-related simplifications

- Keyword search is `ILIKE '%q%'` for now — good enough at MVP data volumes. Spec §17 (Postgres full-text search with `to_tsvector`/`plainto_tsquery` and a GIN index) is the next step once query latency or ranking becomes an issue.
- No semantic search, no match scoring, no per-user ranking yet — that's Phase 5.
- No "sort by match score" option in the UI yet (spec §29) because there's no user profile / match score to sort by yet.

### Deliberate scope cuts in this slice

- `User` / `UserProfile` / `UserSkills` / `Applications` tables — not created yet (spec §7.1–7.3, §25 land in Phase 1/6).
- Company fields `legal_name, industry, employee_count, headquarters, linkedin_url, website_url` — omitted from the `Company` table until enrichment (spec §27) is built, rather than carried as permanently-null columns.
- Job `team` field — dropped; Greenhouse doesn't distinguish it from `department`.
- Dedup Levels 2–4 (canonical URL / company+title+location / description similarity) — deferred; spec §30 lists "perfect deduplication" as an explicit MVP non-goal. Only Level 1 (exact `provider + source_identifier + external_job_id`) is implemented.
- `discover()` on `JobProvider` (crawling a company's own site to find its ATS board — Mode A) raises `NotImplementedError`. Only Mode D (user-submitted source URL) is wired up.
- Location/salary normalization (spec §13/§14) is not implemented as separate structured fields yet — `location` is stored as the raw string from the source; `salary_min/max/currency` are populated only when Greenhouse provides structured salary data (never invented).
- No frontend, no search (full-text or semantic), no matching/scoring, no application tracking, no notifications, no recruiter enrichment.

## Not built yet (by phase)

| Phase | Status |
|---|---|
| 5 — Profile and Matching | Not started |
| 6 — Application Workflow | Not started |
| 7 — Scheduled Collection (cron-triggered sync) | Not started — sync is currently triggered manually via `POST /sources/{id}/sync` |
| Providers beyond Greenhouse (Ashby, Lever, Workable, ...) | Not started — `providers/registry.py` is written to make adding one straightforward |
| Postgres full-text search (spec §17) | Not started — current search uses ILIKE; upgrade when data volume warrants |

## Local development

See [README.md](../README.md).
