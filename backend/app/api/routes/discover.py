"""Extract and validate candidate Greenhouse job boards from arbitrary text.

The user pastes anything (Google search results, LinkedIn posts, articles, their own
curated list) and we extract ``boards.greenhouse.io/<token>`` URLs, then hit the
Greenhouse public API to keep only ones with real published jobs. The frontend can
show a preview so the user picks which boards to actually add.

An optional auto-search path is layered on top: when an Anthropic API key is
configured we can also call Claude with its built-in web-search tool to *find*
new URLs from a natural-language query. If the key is missing the extraction path
still works — just paste from any source.
"""
from __future__ import annotations

import concurrent.futures
import os
import re
from dataclasses import dataclass

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import JobSource

router = APIRouter(prefix="/discover", tags=["discover"])

_TOKEN_RE = re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9\-]+)")


@dataclass
class Candidate:
    token: str
    name: str
    job_count: int


class ExtractRequest(BaseModel):
    text: str  # any text — URLs, HTML, plaintext, mixed


class SearchRequest(BaseModel):
    query: str  # natural-language query, e.g. "climate energy startups"


class DiscoverCandidate(BaseModel):
    token: str
    company_name: str
    source_url: str
    job_count: int
    already_registered: bool


class DiscoverResponse(BaseModel):
    candidates: list[DiscoverCandidate]
    total_tokens_seen: int  # how many unique tokens were extracted before validation
    filtered_out: int  # how many had 0 jobs or 404'd


def _existing_tokens(db: Session) -> set[str]:
    return {
        row.source_identifier
        for row in db.scalars(
            select(JobSource).where(JobSource.provider == "greenhouse")
        )
    }


def _validate(token: str) -> Candidate | None:
    try:
        r = httpx.get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
            timeout=6.0,
        )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    jobs = data.get("jobs", [])
    if not jobs:
        return None
    company_name = jobs[0].get("company_name") or token
    return Candidate(token=token, name=company_name, job_count=len(jobs))


def _validate_and_shape(tokens: set[str], existing: set[str]) -> DiscoverResponse:
    if not tokens:
        return DiscoverResponse(candidates=[], total_tokens_seen=0, filtered_out=0)

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        results = list(pool.map(_validate, tokens))

    valid = [c for c in results if c is not None]
    valid.sort(key=lambda c: c.job_count, reverse=True)

    candidates = [
        DiscoverCandidate(
            token=c.token,
            company_name=c.name,
            source_url=f"https://boards.greenhouse.io/{c.token}",
            job_count=c.job_count,
            already_registered=c.token in existing,
        )
        for c in valid
    ]
    return DiscoverResponse(
        candidates=candidates,
        total_tokens_seen=len(tokens),
        filtered_out=len(tokens) - len(valid),
    )


@router.post("/extract", response_model=DiscoverResponse)
def extract(payload: ExtractRequest, db: Session = Depends(get_db)) -> DiscoverResponse:
    """Pull Greenhouse tokens from arbitrary pasted text and validate them."""
    tokens = set(_TOKEN_RE.findall(payload.text or ""))
    return _validate_and_shape(tokens, _existing_tokens(db))


@router.post("/search", response_model=DiscoverResponse)
def search(payload: SearchRequest, db: Session = Depends(get_db)) -> DiscoverResponse:
    """Find Greenhouse boards matching a query using Anthropic's web-search tool.

    Requires ANTHROPIC_API_KEY. This is a convenience layer over /discover/extract —
    Claude does the searching, we still validate every URL it surfaces against the
    Greenhouse API before returning it, so hallucinated tokens get filtered out.
    """
    query = payload.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query cannot be empty.")
    if not os.getenv("ANTHROPIC_API_KEY", "").strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "ANTHROPIC_API_KEY is not set. Set it to enable auto-search, "
                "or use the paste-text option instead."
            ),
        )

    # Import lazily so the app still boots without the SDK when discover isn't used.
    from anthropic import Anthropic, APIError

    client = Anthropic()
    prompt = (
        f"Search the web for `site:boards.greenhouse.io {query}` and return every unique "
        "boards.greenhouse.io/<token> URL you find in the results, one per line, nothing else. "
        "Prefer smaller/less-known companies. Return at least 10 URLs if possible."
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        raise HTTPException(status_code=502, detail=f"Anthropic API error: {exc}")

    # Concatenate any text blocks in the response and extract tokens from them.
    text_blob = "\n".join(
        getattr(block, "text", "") for block in msg.content if getattr(block, "type", "") == "text"
    )
    tokens = set(_TOKEN_RE.findall(text_blob))
    return _validate_and_shape(tokens, _existing_tokens(db))
