# Job Intelligence Platform — Product Strategy, Technical Architecture, and Implementation Specification

Version: 1.0
Status: Build Specification
Primary Objective: Discover, normalize, search, rank, and manage job opportunities sourced directly from company career infrastructure and ATS platforms.

> This document is the original product/architecture spec as provided by the user. See [ARCHITECTURE.md](./ARCHITECTURE.md) for what has actually been built so far and the current implementation status against this spec.

## 1. Executive Summary

### 1.1 The Problem

The modern job market is fragmented. Many companies publish job openings directly through applicant tracking systems and company-specific career infrastructure rather than relying exclusively on major job boards such as LinkedIn or Indeed. Examples include: Greenhouse, Lever, Ashby, Workday, Workable, BambooHR, Breezy, SmartRecruiters, Recruitee, Jobvite, iCIMS, Teamtailor, Pinpoint, and custom company career pages.

A job seeker who relies primarily on LinkedIn or Indeed is therefore potentially missing a significant portion of the available market. The current process is inefficient: search LinkedIn, search Indeed, search Google, search company websites individually, search ATS-specific URLs, discover a company, find its careers page, search for relevant positions, determine whether the job is new, determine whether the job is relevant, determine whether the user is qualified, find the hiring manager or recruiter, tailor the resume, write an application message, track the application. This is fragmented and repetitive.

### 1.2 The Product

The Job Intelligence Platform is a job discovery and application intelligence system that discovers jobs directly from company career infrastructure, normalizes them into a unified data model, makes them searchable, identifies relevant opportunities, ranks them against a user's profile, and supports the complete application workflow.

The product should not initially be positioned as another generic job board. Its core value proposition is: find relevant jobs directly from the source, identify opportunities early, and help the user decide and act faster.

## 2. Strategic Product Thesis

The platform should be built around three layers of value.

**Layer 1: Discovery** — Find jobs that are difficult to discover through traditional job boards (Company website → Career page → ATS platform → Job posting). The system should detect and index those jobs.

**Layer 2: Intelligence** — A raw job posting is not enough. The platform should answer: Is this job actually relevant? How closely does it match the user's experience? What are the strongest matching qualifications? What are the likely gaps? Is the posting new? Is the company worth pursuing? Who is likely involved in hiring? Has this position appeared before?

**Layer 3: Action** — The user should be able to move from Discover → Evaluate → Prioritize → Tailor → Apply → Track without leaving the application unnecessarily.

## 3. Initial Product Scope

The first version should focus on a single user and a highly effective personal workflow.

- **Job Discovery**: company career page discovery, ATS detection, ATS-specific job collection, job normalization, scheduled updates.
- **Job Search**: keyword search, title filtering, location filtering, remote filtering, salary filtering, company filtering, technology/skill filtering, seniority filtering.
- **Job Intelligence**: match scoring, resume/profile comparison, skill extraction, requirement extraction, match explanations, potential gap identification, job freshness.
- **Application Workflow**: save jobs, mark interested, mark applied, track application stages, add notes, store recruiter/hiring manager information, generate application-specific materials.

## 4. Product Principles

**Principle 1: Source data should be as close to the employer as possible.** Preferred source hierarchy: (1) Official ATS API, (2) Official structured feed, (3) Public JSON endpoint, (4) JSON-LD structured data, (5) Server-rendered HTML, (6) Browser-rendered HTML, (7) Headless browser automation. Avoid browser automation unless necessary.

**Principle 2: Provider-specific complexity belongs behind adapters.** The rest of the system should not care whether a job came from Greenhouse, Lever, Ashby, or Workday. Every connector should produce a common internal representation.

**Principle 3: Data collection and product experience must be separated.** Discovery → Collection → Normalization → Deduplication → Enrichment → Search → Matching → Application Workflow.

**Principle 4: Build a modular monolith first.** Do not begin with microservices. The initial architecture should be a modular monolith with asynchronous workers:

```
job-intelligence/
├── backend/
│   ├── api/
│   ├── domain/
│   ├── providers/
│   ├── discovery/
│   ├── normalization/
│   ├── deduplication/
│   ├── enrichment/
│   ├── matching/
│   ├── applications/
│   ├── notifications/
│   └── search/
├── frontend/
├── workers/
├── infrastructure/
├── tests/
└── docs/
```

This allows the system to be split later only when required.

## 5. Recommended Technology Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Pydantic — Python is appropriate because the system will eventually require API integrations, crawling, HTML parsing, data processing, NLP, embeddings, and AI integrations.
- **Database**: PostgreSQL as the primary system of record — relational tables, full-text search initially, PostgreSQL extensions where useful, pgvector for semantic search later.
- **Background Processing**: Redis + Celery (or Dramatiq) — API → Queue → Worker → Provider connector → Database.
- **Frontend**: React, Next.js, TypeScript — a responsive web application.
- **Deployment**: Docker, PostgreSQL, Redis, Backend, Worker, Frontend. Do not require Kubernetes for the first release. `docker compose up` for local development.

## 6. High-Level System Architecture

```
Frontend (Search / Jobs / Applications)
        ↓
API Layer (Auth, Jobs, Companies, Search, Matching, Applications)
        ↓
   ┌────┴────┐
   ▼         ▼
PostgreSQL   Redis (Queue, Cache, Locks)
                 ↓
           Worker System
                 ↓
   ┌─────────────┼─────────────┐
Greenhouse     Lever         Ashby
Connector    Connector    Connector
                 ↓
   Normalization / Deduplication / Enrichment
```

## 7. Core Domain Model

### 7.1 User
`id, email, name, created_at, updated_at`

### 7.2 User Profile
`id, user_id, headline, summary, years_experience, preferred_locations, remote_preference, minimum_salary, maximum_salary, target_titles, target_industries, created_at, updated_at`

### 7.3 User Skills
`id, user_profile_id, skill_name, skill_type, proficiency, years_experience, source`

### 7.4 Company
`id, name, legal_name, domain, description, industry, employee_count, headquarters, linkedin_url, website_url, created_at, updated_at`

### 7.5 Job Source
A source represents a specific career infrastructure endpoint.
`id, company_id, provider, source_url, source_identifier, status, last_successful_sync, last_attempted_sync, last_error, created_at, updated_at`

Example: `provider: greenhouse`, `source_identifier: acme`, `source_url: https://boards.greenhouse.io/acme`

### 7.6 Job
`id, company_id, job_source_id, external_job_id, canonical_url, title, description, location, remote_type, employment_type, department, team, salary_min, salary_max, salary_currency, posted_at, first_seen_at, last_seen_at, last_content_change_at, status, content_hash, created_at, updated_at`

Possible status values: `active, closed, expired, unknown`

## 8. Provider Adapter Architecture

Every provider must implement a shared interface:

```python
class JobProvider(ABC):
    @abstractmethod
    def detect(self, url: str) -> bool: ...
    @abstractmethod
    def discover(self, company_url: str): ...
    @abstractmethod
    def fetch_jobs(self, source): ...
    @abstractmethod
    def fetch_job(self, job_url: str): ...
    @abstractmethod
    def normalize(self, raw_job): ...
```

A provider implementation should never leak provider-specific fields into the rest of the application: `GreenhouseProvider → RawGreenhouseJob → GreenhouseNormalizer → NormalizedJob → Database`.

## 9. Provider Implementation Strategy

- **Phase 1**: Greenhouse, Ashby, Lever, Workable — initial coverage-to-effort ratio.
- **Phase 2**: SmartRecruiters, Recruitee, Teamtailor, Breezy, BambooHR.
- **Phase 3**: Workday, iCIMS, Jobvite, custom enterprise career sites. Workday should not be the first integration.

## 10. Company and ATS Discovery

Given a company, where are its jobs? Workflow: fetch company homepage → extract career-related links → inspect links and redirects → detect ATS provider → create JobSource → begin indexing.

**Career Page Detection**: look for links containing `career/careers/jobs/job/join-us/join/work-with-us/opportunities/employment`, then inspect anchors, iframes, scripts, redirects, embedded JSON, external domains.

**ATS Detection** should use multiple signals:
- Hostname (e.g. `boards.greenhouse.io`, `jobs.ashbyhq.com`, `jobs.lever.co`, `apply.workable.com`)
- HTML content (search for `greenhouse`, `lever`, `ashby`, `workday`, `bamboohr`)
- Provider-specific JavaScript assets
- Network requests, for browser-rendered applications

## 11. Discovery Modes

- **Mode A: Direct Company Search** — user enters a company name; system searches → finds website → finds careers page → detects ATS → indexes jobs.
- **Mode B: Company List Import** — CSV of `company_name,domain`, processed asynchronously.
- **Mode C: Search Engine Discovery** — discover ATS-hosted career pages using external search infrastructure (e.g. `site:boards.greenhouse.io`), abstracted behind a provider interface.
- **Mode D: User-Submitted Source** — user pastes a URL like `https://boards.greenhouse.io/company`; the system detects the provider and indexes the source. Extremely useful for the MVP.

## 12. Job Normalization

```python
class NormalizedJob:
    source_provider: str
    source_job_id: str
    company_name: str
    title: str
    description: str
    location: str | None
    remote_type: str | None
    employment_type: str | None
    department: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    posted_at: datetime | None
    canonical_url: str
```

## 13. Location Normalization

Raw location strings (`Remote - United States`, `United States - Remote`, `Remote`, `New York, NY`, `New York City`, `NYC`, `Austin, Texas`, `Austin, TX`) normalize into `country, state, city, remote_type, remote_regions`. Remote types: `remote, hybrid, onsite, unknown`.

## 14. Salary Normalization

Salary data may appear as `$120,000 - $150,000`, `120k-150k USD`, `$60-$70/hour`, `Competitive`. Preserve the raw value and normalize when possible into `salary_min, salary_max, salary_currency, salary_period, salary_raw`. Salary periods: `hourly, weekly, monthly, annual, unknown`. Do not invent salary values when the source does not provide them.

## 15. Deduplication

- **Level 1: Exact Source Match** — same `provider + source_identifier + external_job_id`. Strongest match.
- **Level 2: Canonical URL** — same normalized URL.
- **Level 3: Company + Title + Location** — potential duplicate.
- **Level 4: Description Similarity** — normalized text, content hash, similarity comparison.

## 16. Job Freshness

Distinguish `source_posted_at` from `first_seen_at`/`last_seen_at`/`last_content_change_at`. The UI should prioritize "First seen 3 hours ago" — often more useful to a job seeker than the source's own posted date.

## 17. Search Architecture

Initial search uses PostgreSQL full-text search over `title, description, company_name, department, location, skills` (`to_tsvector('english', ...)`). Introduce Elasticsearch/OpenSearch/Meilisearch/Typesense only when PostgreSQL is no longer sufficient.

## 18. Search Filters

Title, Location (Remote/Hybrid/Onsite/geography), Salary (min/max), Company (company/industry/employee count), Job Characteristics (full-time/part-time/contract), Freshness (today/last 3 days/last 7 days/last 30 days).

## 19. Skills and Requirement Extraction

Extract Required Skills, Preferred Skills, Experience Requirements, Education, Responsibilities — distinguishing `required`, `preferred`, `responsibility`.

## 20. User Profile and Resume Intelligence

The user provides resume, LinkedIn profile content, skills, experience, accomplishments, preferred roles, salary preferences, location preferences. The system builds a structured profile with skills and confidence scores.

## 21. Job Match Scoring

The match score should be explainable, not a mysterious AI number — Strong Matches, Partial Matches, Potential Gaps. Initial scoring model (weights configurable): Title Alignment 20%, Required Skills 30%, Experience 20%, Industry 10%, Seniority 10%, Location 5%, Salary 5%.

## 22. Semantic Matching

Keyword matching is insufficient (e.g. "customer lifecycle automation" vs. "customer journey orchestration"). Use embeddings: User Profile → Embedding, Job Description → Embedding, Similarity → Match Score. Use semantic matching as one signal, not the entire scoring system.

## 23. Match Explanation Engine

Every match should answer "Why is this job relevant?" with concrete, specific reasons — more valuable than a bare "AI Score: 92%".

## 24. Application Tracking

Pipeline: Discovered → Interested → Researching → Applied → Recruiter Contacted → Recruiter Screen → Interview → Final Interview → Offer → Rejected → Withdrawn. A job can also be `Ignored`.

## 25. Application Record

`id, user_id, job_id, status, applied_at, resume_version, cover_letter_version, recruiter_name, recruiter_url, hiring_manager_name, hiring_manager_url, notes, created_at, updated_at`

## 26. Application Materials

Resume Version, Cover Letter, Personal Note, LinkedIn Message, Email, Interview Preparation — versioned per application.

## 27. Recruiter and Hiring Manager Discovery

A separate enrichment feature, not a requirement for the initial job ingestion pipeline. Given Company/Job Title/Department, help identify likely Recruiter/Hiring Manager/Department Leader.

## 28. Notifications

User-defined saved searches with filters (salary, company size, geography, freshness, match score threshold), delivered via Email, In-app, Daily digest, or Immediate alert.

## 29. Recommended MVP

- **Sources**: Greenhouse, Ashby, Lever, Workable
- **Discovery**: add company manually, add ATS URL manually, detect provider, index jobs
- **Job Search**: full-text search, filters, sort by freshness, sort by match score
- **User Profile**: resume upload, structured skill profile
- **Matching**: match score, strong matches, potential gaps, explanation
- **Workflow**: save job, track status, add notes, mark applied

## 30. MVP Non-Goals

Do not initially build: universal crawling of the entire internet, every ATS provider, automatic application submission, browser automation for job applications, complex multi-tenant enterprise architecture, Kubernetes, fully autonomous AI agents, perfect job deduplication, perfect salary extraction, perfect recruiter identification. The goal is to build a reliable core.

## 31. Recommended Development Phases

- **Phase 0**: Repository and Architecture — README, ARCHITECTURE, PRODUCT_SPEC, CONTRIBUTING; backend/frontend/workers/tests/infrastructure/docs directories; Docker, PostgreSQL, Redis, API, Frontend, CI/CD.
- **Phase 1**: Core Data Model — Users, Companies, Job Sources, Jobs, User Profiles, Skills, Applications; migrations; seed data; repository tests.
- **Phase 2**: Provider Framework — shared interface, mocked fixtures, contract tests.
- **Phase 3**: First Provider — Greenhouse end-to-end (Source → Fetch → Normalize → Deduplicate → Persist → Search). Do not implement all providers at once.
- **Phase 4**: Search UI — Search Bar, Filters, Job List, Job Detail.
- **Phase 5**: Profile and Matching — Resume Upload → Text Extraction → Profile Extraction → Skill Extraction → Job Matching. Start deterministic, then add semantic matching.
- **Phase 6**: Application Workflow — Save → Interested → Applied → Interview → Offer, plus notes/recruiter/hiring manager/application materials.
- **Phase 7**: Scheduled Collection — Scheduled Job → Source Sync → New/Changed/Removed Jobs, via background workers.

## 32. Testing Strategy

- **Unit Tests**: URL detection, provider detection, salary parsing, location normalization, job normalization, content hashing, deduplication, match scoring.
- **Provider Contract Tests**: every provider passes the same contract — can detect source, can fetch jobs, can normalize job, can handle empty results, can handle malformed data, can handle API errors.
- **Integration Tests**: Provider → Worker → Database → API → Frontend.
- **Failure Tests**: HTTP 429, HTTP 500, timeout, malformed JSON, changed schema, empty job list, duplicate job, deleted job, missing salary, missing location.

## 33. Observability

Every provider should expose metrics: `sync_attempts, sync_successes, sync_failures, jobs_found, jobs_added, jobs_updated, jobs_removed, average_duration`.

## 34. Rate Limiting and Reliability

Respect provider limitations, avoid unnecessary requests, cache results, use exponential backoff, implement retries, use provider-specific request limits. Example backoff: attempt 1 immediate, attempt 2 → 2s, attempt 3 → 8s, attempt 4 → 30s. Do not aggressively crawl. Prioritize known active sources → recently active sources → new discovery.

## 35. Legal and Operational Considerations

Review before public commercialization: Terms of service, API terms, robots.txt, copyright, data retention, privacy, user resume data, third-party platform restrictions. Prefer official public APIs whenever available. The platform should avoid representing itself as the employer or application destination — the canonical application URL should remain available.

## 36. Security Requirements

Encrypted transport, secure authentication, password hashing, secrets outside source code, database backups, access controls, secure file storage, signed upload URLs, audit logging. Resume files should not be stored directly in the application database — use object storage.

## 37. AI-Assisted Development Strategy

The application should be designed for iterative implementation by an AI coding agent. The repository should contain `/docs` with PRODUCT_SPEC.md, ARCHITECTURE.md, DATA_MODEL.md, PROVIDER_GUIDE.md, API_SPEC.md, DEVELOPMENT_PLAN.md. Every major feature should have: Requirement → Design → Implementation → Tests → Documentation.

## 38. Recommended AI Coding Agent Workflow

**Step 1**: Ask the agent to inspect the repository — review structure, identify current architecture/technologies/missing components/risks/recommended implementation order, return a written plan without modifying code.

**Step 2**: Implement one vertical slice (e.g. Greenhouse provider end-to-end: detection, source configuration, fetching, normalization, persistence, deduplication, tests, error handling — do not modify unrelated modules).

**Step 3**: Run tests — full suite, fix only failures related to the current implementation, do not rewrite unrelated architecture.

**Step 4**: Add the next provider (e.g. Ashby) using the existing provider abstraction — do not duplicate architecture, reuse the common normalized job model, add provider-specific tests.

## 39. The First Development Prompt

> You are the lead architect for a new Job Intelligence Platform. The product objective is to discover job postings directly from company career infrastructure and ATS providers, normalize them into a unified schema, make them searchable, score them against a user's profile, and support application tracking. Before writing code: review the entire repository, identify the current stack and architecture, compare the existing implementation against the product specification, identify missing infrastructure, propose a phased implementation plan, identify architectural risks, and do not make code changes yet. Return a detailed implementation plan with proposed directory structure, database schema, service boundaries, provider adapter architecture, testing strategy, deployment approach, and the first vertical slice to implement.

## 40. First Implementation Prompt

> Implement the first complete vertical slice of the Job Intelligence Platform. Scope: PostgreSQL database setup; Company model; JobSource model; Job model; Greenhouse provider adapter; provider detection; job normalization; job persistence; content hashing; basic deduplication; background sync task; API endpoint to create a source; API endpoint to sync a source; API endpoint to list jobs; tests for all core behavior. Requirements: follow the existing architecture, use typed models, keep provider-specific logic isolated, make sync operations idempotent, handle API failures gracefully, add structured logging, do not add unnecessary infrastructure, do not implement other ATS providers yet. Before modifying files, explain the planned changes, then implement them, then run the test suite and report results.

## 41. Long-Term Product Vision

The ultimate product should become a personalized job intelligence system where the user can say: "Find me new remote Customer Success Operations roles — United States, $130,000+, SaaS companies, 100–5,000 employees, posted within the last 72 hours, at least an 80% match to my background." The system discovers sources → collects jobs → normalizes → deduplicates → analyzes requirements → compares to profile → ranks opportunities → notifies user → generates an application strategy (why this job, why you match, where you are weak, what to emphasize, who to contact, what resume version to use, what message to send, what questions to prepare for). That is a much more valuable product than a traditional job board.

## 42. Final Strategic Recommendation

Build in this order: (1) Personal job discovery, (2) Reliable ATS integrations, (3) Unified job database, (4) Search and filtering, (5) Resume/profile matching, (6) Application tracking, (7) Notifications, (8) Recruiter and hiring manager intelligence, (9) AI-assisted application preparation, (10) Broader company and ATS discovery.

Do not begin by attempting to index every job on the internet. Begin by proving this workflow: I know a company → I find its career infrastructure → I find its jobs → I search them → I identify the best opportunities → I apply more effectively. Once that workflow is reliable, expand the discovery engine.

The strongest version of the product is: a system that finds opportunities other job boards miss, explains why they are relevant, and helps the user take the next action.
