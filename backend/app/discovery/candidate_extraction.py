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
# Greenhouse:      boards.greenhouse.io/<token>
# Ashby:           jobs.ashbyhq.com/<orgId>  or  api.ashbyhq.com/posting-api/job-board/<orgId>
# Lever:           jobs.lever.co/<slug>       or  api.lever.co/v0/postings/<slug>
# SmartRecruiters: jobs.smartrecruiters.com/<companyId>   or  api.smartrecruiters.com/v1/companies/<id>
# BreezyHR:        <companyId>.breezy.hr    (subdomain-based — first label)
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("greenhouse", re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9\-_]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([a-zA-Z0-9\-_]+)")),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([a-zA-Z0-9\-_]+)")),
    ("lever", re.compile(r"jobs\.lever\.co/([a-zA-Z0-9\-_]+)")),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([a-zA-Z0-9\-_]+)")),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([a-zA-Z0-9\-_]+)")),
    ("smartrecruiters", re.compile(r"api\.smartrecruiters\.com/v1/companies/([a-zA-Z0-9\-_]+)")),
    ("breezyhr", re.compile(r"https?://([a-zA-Z0-9\-_]+)\.breezy\.hr")),
    ("workable", re.compile(r"apply\.workable\.com/([a-zA-Z0-9\-_]+)")),
    ("bamboohr", re.compile(r"https?://([a-zA-Z0-9\-_]+)\.bamboohr\.com")),
    # Workday: encoded (host, tenant, site) triple. Matches the FULL URL — we don't extract
    # a token here because the identifier is composite. See _extract_workday_ids below.
]

# Tokens that would appear in extracted matches but aren't real orgIds. Anything the URL
# shape technically allows but that's really a route segment or a UUID job id.
_EXCLUDED_TOKENS = {
    "embed",  # boards.greenhouse.io/embed/job_board?for=...
    "posting-api",
    "job-board",
    "v0",
    "postings",
    "v1",
    "companies",
    "www",
    "api",
    "app",
}


_WORKDAY_URL_RE = re.compile(
    r"https?://([a-z0-9\-]+)\.([a-z0-9]+\.myworkdayjobs\.com)/(?:[a-z]{2}(?:-[A-Z]{2})?/)?([a-zA-Z0-9\-_]+)",
    re.IGNORECASE,
)


def _extract_workday(text: str) -> set[TokenMatch]:
    """Workday's identifier is a (tenant, host, site) triple encoded as tenant||host||site."""
    from app.providers.workday.client import WorkdayClient

    out: set[TokenMatch] = set()
    seen: set[str] = set()
    for m in _WORKDAY_URL_RE.finditer(text or ""):
        tenant = m.group(1).lower()
        # Full host is <tenant>.<wdN>.myworkdayjobs.com
        host = f"{tenant}.{m.group(2).lower()}"
        site = m.group(3)
        if site in _EXCLUDED_TOKENS:
            continue
        # Route segments that aren't real site names.
        if site.lower() in {"job", "jobs", "wday", "cxs"}:
            continue
        ident = WorkdayClient.encode_identifier(host, tenant, site)
        if ident in seen:
            continue
        seen.add(ident)
        out.add(TokenMatch(provider="workday", token=ident))
    return out


def extract_tokens(text: str) -> set[TokenMatch]:
    """Return all unique (provider, token) pairs found in ``text``."""
    out: set[TokenMatch] = set()
    for provider, pattern in _PATTERNS:
        for m in pattern.findall(text or ""):
            token = m.strip()
            if not token or token in _EXCLUDED_TOKENS:
                continue
            # Ashby / Workable job IDs are UUIDs or shortcodes; skip those.
            if provider == "ashby" and _looks_like_uuid(token):
                continue
            # Workable single-job URLs: apply.workable.com/j/<shortcode> — token would be "j".
            if provider == "workable" and token in {"j"}:
                continue
            out.add(TokenMatch(provider=provider, token=token))
    # Workday's identifier is composite, extracted separately.
    out |= _extract_workday(text)
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


def _validate_workable(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(
            f"https://apply.workable.com/api/v1/widget/accounts/{token}",
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
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    if not jobs:
        return None
    name = data.get("name") or token.replace("-", " ").replace("_", " ").title()
    return (name, len(jobs))


def _validate_bamboohr(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(
            f"https://{token}.bamboohr.com/careers/list",
            headers={"User-Agent": "job-intel/0.1", "Accept": "application/json"},
            timeout=8.0,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    jobs = data.get("result", [])
    if not jobs:
        return None
    name = token.replace("-", " ").replace("_", " ").title()
    return (name, len(jobs))


def _validate_workday(token: str) -> tuple[str, int] | None:
    try:
        from app.providers.workday.client import WorkdayClient

        tenant, host, site = WorkdayClient.decode_identifier(token)
    except ValueError:
        return None
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    try:
        r = httpx.post(
            url,
            json={"limit": 1, "offset": 0, "searchText": "", "appliedFacets": {}},
            headers={"User-Agent": "job-intel/0.1", "Accept": "application/json"},
            timeout=12.0,
        )
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except ValueError:
        return None
    total = int(data.get("total") or 0)
    if total == 0:
        return None
    name = tenant.replace("-", " ").replace("_", " ").title()
    return (name, total)


def _validate_smartrecruiters(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(
            f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=1",
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
    total = int(data.get("totalFound") or 0)
    if total == 0:
        return None
    # Prefer the display name from the first posting when available.
    content = data.get("content") or []
    if content:
        name = (content[0].get("company") or {}).get("name") or token
    else:
        name = token
    return (name, total)


def _validate_breezyhr(token: str) -> tuple[str, int] | None:
    try:
        r = httpx.get(f"https://{token}.breezy.hr/json", timeout=8.0)
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        jobs = r.json()
    except ValueError:
        return None
    if not isinstance(jobs, list) or not jobs:
        return None
    # BreezyHR jobs carry a company object with a name field; fall back to a slug-derived name.
    company_name = (jobs[0].get("company") or {}).get("name") if isinstance(jobs[0], dict) else None
    name = company_name or token.replace("-", " ").replace("_", " ").title()
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
    "smartrecruiters": _validate_smartrecruiters,
    "breezyhr": _validate_breezyhr,
    "workable": _validate_workable,
    "bamboohr": _validate_bamboohr,
    "workday": _validate_workday,
}


def _source_url(match: TokenMatch) -> str:
    if match.provider == "greenhouse":
        return f"https://boards.greenhouse.io/{match.token}"
    if match.provider == "ashby":
        return f"https://jobs.ashbyhq.com/{match.token}"
    if match.provider == "lever":
        return f"https://jobs.lever.co/{match.token}"
    if match.provider == "smartrecruiters":
        return f"https://jobs.smartrecruiters.com/{match.token}"
    if match.provider == "breezyhr":
        return f"https://{match.token}.breezy.hr"
    if match.provider == "workable":
        return f"https://apply.workable.com/{match.token}"
    if match.provider == "bamboohr":
        return f"https://{match.token}.bamboohr.com"
    if match.provider == "workday":
        try:
            from app.providers.workday.client import WorkdayClient
            _, host, site = WorkdayClient.decode_identifier(match.token)
            return f"https://{host}/{site}"
        except ValueError:
            return ""
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
