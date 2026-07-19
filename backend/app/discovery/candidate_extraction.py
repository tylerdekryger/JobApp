"""Extract and validate candidate ATS job-board tokens from arbitrary text.

Shared by both the /discover route (user-driven paste) and the scheduled
auto-discover task. Each provider has its own URL pattern + validation call,
but the extraction + validation shape is the same.
"""
from __future__ import annotations

import concurrent.futures
import re
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class TokenMatch:
    provider: str  # "greenhouse" | "ashby"
    token: str


@dataclass
class Candidate:
    provider: str
    token: str
    name: str
    job_count: int
    source_url: str


# Regexes for each provider's public URL shape.
# Greenhouse:  boards.greenhouse.io/<token>
# Ashby:       jobs.ashbyhq.com/<orgId>  or  api.ashbyhq.com/posting-api/job-board/<orgId>
# Lever:       jobs.lever.co/<slug>       or  api.lever.co/v0/postings/<slug>
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9\-_]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9\-_]+)")),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-zA-Z0-9\-_]+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([a-zA-Z0-9\-_]+)")),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([a-zA-Z0-9\-_]+)")),
]

# Tokens that would appear in extracted matches but aren't real orgIds. Anything the URL
# shape technically allows but that's really a route segment or a UUID job id.
_EXCLUDED_TOKENS = {
    "embed",  # boards.greenhouse.io/embed/job_board?for=...
    "posting-api",
    "job-board",
    "v0",
    "postings",
}


def extract_tokens(text: str) -> set[TokenMatch]:
    """Return all unique (provider, token) pairs found in ``text``."""
    out: set[TokenMatch] = set()
    for provider, pattern in _PATTERNS:
        for m in pattern.findall(text or ""):
            token = m.strip()
            if not token or token in _EXCLUDED_TOKENS:
                continue
            # Ashby job IDs are UUIDs — they follow the org in the URL but shouldn't be
            # captured as separate orgs. The regex here captures the FIRST segment after
            # the host, which is already the orgId; UUIDs will just fail validation later
            # if they slip through, but this guard avoids the wasted API call.
            if provider == "ashby" and _looks_like_uuid(token):
                continue
            out.add(TokenMatch(provider=provider, token=token))
    return out


def _looks_like_uuid(s: str) -> bool:
    # e.g. "d3bc1ced-3ce4-4086-a050-555055dbb1ff"
    return bool(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", s))


def _validate_greenhouse(token: str) -> tuple[str, int] | None:
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
        jobs = r.json().get("jobs", [])
    except ValueError:
        return None
    if not jobs:
        return None
    name = jobs[0].get("company_name") or token
    return (name, len(jobs))


def _validate_lever(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(f"https://api.lever.co/v0/postings/{token}?mode=json", timeout=8.0)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    jobs = data if isinstance(data, list) else []
    if not jobs:
        return None
    # Lever doesn't return a company_name on each posting; derive from the slug.
    name = token.replace("-", " ").replace("_", " ").title()
    return (name, len(jobs))


def _validate_ashby(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false",
            timeout=8.0,
        )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    jobs = [j for j in data.get("jobs", []) if j.get("isListed", True)]
    if not jobs:
        return None
    # Ashby doesn't return company_name on jobs; derive a display name from the token so
    # the UI still has something reasonable to show ("linear" → "Linear").
    name = token.replace("-", " ").replace("_", " ").title()
    return (name, len(jobs))


_VALIDATORS = {
    "greenhouse": _validate_greenhouse,
    "ashby": _validate_ashby,
    "lever": _validate_lever,
}


def _source_url(match: TokenMatch) -> str:
    if match.provider == "greenhouse":
        return f"https://boards.greenhouse.io/{match.token}"
    if match.provider == "ashby":
        return f"https://jobs.ashbyhq.com/{match.token}"
    if match.provider == "lever":
        return f"https://jobs.lever.co/{match.token}"
    return ""


def validate_candidates(matches: set[TokenMatch]) -> list[Candidate]:
    """Hit each provider's public API in parallel; keep only tokens with >0 jobs."""
    if not matches:
        return []

    def _run(m: TokenMatch) -> Candidate | None:
        result = _VALIDATORS.get(m.provider, lambda _t: None)(m.token)
        if result is None:
            return None
        name, count = result
        return Candidate(
            provider=m.provider,
            token=m.token,
            name=name,
            job_count=count,
            source_url=_source_url(m),
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
        results = list(pool.map(_run, matches))

    return [c for c in results if c is not None]
