"""Extract and validate candidate ATS job boards from arbitrary text.

Supports both Greenhouse (``boards.greenhouse.io/<token>``) and Ashby
(``jobs.ashbyhq.com/<orgId>``) URLs. The user pastes anything — Google results,
LinkedIn posts, articles, their own list — and we pull out matching URLs, then
hit each provider's public API to keep only ones with real published jobs. The
frontend previews the survivors so the user picks which boards to actually add.

An optional auto-search path is layered on top: when a search-capable key is
configured (Tavily preferred, then Gemini/Anthropic web search), we can also
call it to *find* new URLs from a natural-language query. If none of those
keys are set, the paste-text path still works.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.discovery.candidate_extraction import (
    Candidate,
    TokenMatch,
    extract_tokens,
    validate_candidates,
)
from app.domain.models import JobSource

router = APIRouter(prefix="/discover", tags=["discover"])


class ExtractRequest(BaseModel):
    text: str  # any text — URLs, HTML, plaintext, mixed


class SearchRequest(BaseModel):
    query: str  # natural-language query, e.g. "climate energy startups"


class DiscoverCandidate(BaseModel):
    provider: str
    token: str
    company_name: str
    source_url: str
    job_count: int
    already_registered: bool


class DiscoverResponse(BaseModel):
    candidates: list[DiscoverCandidate]
    total_tokens_seen: int  # unique tokens found before validation
    filtered_out: int  # tokens that had 0 jobs or 404'd


def _existing_by_provider(db: Session) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for row in db.scalars(select(JobSource)):
        out.setdefault(row.provider, set()).add(row.source_identifier)
    return out


def _shape(candidates: list[Candidate], matches: set[TokenMatch], existing: dict[str, set[str]]) -> DiscoverResponse:
    # Rank fatter boards first so the user sees the highest-signal rows above the fold.
    candidates.sort(key=lambda c: c.job_count, reverse=True)
    return DiscoverResponse(
        candidates=[
            DiscoverCandidate(
                provider=c.provider,
                token=c.token,
                company_name=c.name,
                source_url=c.source_url,
                job_count=c.job_count,
                already_registered=c.token in existing.get(c.provider, set()),
            )
            for c in candidates
        ],
        total_tokens_seen=len(matches),
        filtered_out=len(matches) - len(candidates),
    )


@router.post("/extract", response_model=DiscoverResponse)
def extract(payload: ExtractRequest, db: Session = Depends(get_db)) -> DiscoverResponse:
    """Pull provider-specific tokens from pasted text and validate them."""
    matches = extract_tokens(payload.text or "")
    candidates = validate_candidates(matches)
    return _shape(candidates, matches, _existing_by_provider(db))


class RunNowResponse(BaseModel):
    query: str
    tokens_found: int
    new_boards_added: int
    jobs_added: int
    added_tokens: list[str]
    skipped_too_large: list[str] = []
    skipped: str | None = None


@router.post("/run-now", response_model=RunNowResponse)
def run_auto_discover_now() -> RunNowResponse:
    """Trigger the scheduled auto-discover task on demand and return a summary."""
    from app.scheduling.discover_task import run_auto_discover

    if not any(
        os.getenv(k, "").strip() for k in ("TAVILY_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY")
    ):
        raise HTTPException(
            status_code=400,
            detail="No search key set. Add TAVILY_API_KEY (free) to enable auto-discover.",
        )
    stats = run_auto_discover()
    return RunNowResponse(
        query=stats.query,
        tokens_found=stats.tokens_found,
        new_boards_added=stats.new_boards_added,
        jobs_added=stats.jobs_added,
        added_tokens=stats.added_tokens,
        skipped_too_large=stats.skipped_too_large,
        skipped=stats.skipped,
    )


@router.post("/search", response_model=DiscoverResponse)
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> DiscoverResponse:
    """Find candidate boards matching a query. Same fallback chain as the scheduled task."""
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty.")

    from app.scheduling.discover_task import (
        _search_via_anthropic,
        _search_via_gemini,
        _search_via_tavily,
    )

    text_blob = ""
    last_error: str | None = None
    if os.getenv("TAVILY_API_KEY", "").strip():
        text_blob, last_error = _search_via_tavily(query)
    if not text_blob and os.getenv("GEMINI_API_KEY", "").strip():
        text_blob, last_error = _search_via_gemini(query)
    if not text_blob and os.getenv("ANTHROPIC_API_KEY", "").strip():
        text_blob, last_error = _search_via_anthropic(query)
    if not text_blob:
        detail = last_error or (
            "No search key set. Add TAVILY_API_KEY (free) to enable auto-search, "
            "or use the paste-text option instead."
        )
        raise HTTPException(status_code=400, detail=detail)

    matches = extract_tokens(text_blob)
    candidates = validate_candidates(matches)
    return _shape(candidates, matches, _existing_by_provider(db))
