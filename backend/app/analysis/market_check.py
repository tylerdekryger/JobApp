"""Per-job market-context lookup.

Ashby (and Greenhouse to a lesser extent) let posters bump ``publishedAt`` at will —
so a job showing "posted 1 day ago" in our table may in fact have been circulating
for months elsewhere. We cross-check LinkedIn via Tavily and extract two facts:
when the role was posted (with a repost flag if visible) and how many applicants it
has attracted. Everything else is noise for this UI.

Output is stored as a compact multi-line string that renders as bullets in the UI:

    Posted: 3 months ago (reposted)
    Applicants: 200+
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

import httpx


class MarketCheckError(RuntimeError):
    pass


@dataclass
class MarketCheckResult:
    summary: str
    linkedin_url: str | None


# Age like "3 months ago", "1 week ago", "24 hours ago".
_AGE_RE = re.compile(
    r"(\d+\+?\s*(?:hour|day|week|month|year)s?\s+ago)",
    re.IGNORECASE,
)
_REPOSTED_RE = re.compile(r"\breposted\b", re.IGNORECASE)
_CLOSED_RE = re.compile(r"no longer accepting applications", re.IGNORECASE)

# Applicant patterns, most specific first.
_APPLICANT_PATTERNS = [
    re.compile(r"over\s+(\d[\d,]*)\s+(?:people\s+)?applicants?", re.IGNORECASE),
    re.compile(r"(\d[\d,]*)\+\s+applicants?", re.IGNORECASE),
    re.compile(r"be\s+among\s+the\s+first\s+(\d+)\s+applicants?", re.IGNORECASE),
    re.compile(r"(\d[\d,]*)\s+applicants?", re.IGNORECASE),
    re.compile(r"(\d[\d,]*)\s+people\s+clicked\s+apply", re.IGNORECASE),
]


def _extract_age(text: str) -> str | None:
    m = _AGE_RE.search(text)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip().lower()


def _extract_applicants(text: str) -> str | None:
    for pat in _APPLICANT_PATTERNS:
        m = pat.search(text)
        if m:
            n = m.group(1)
            # Distinguish "be among the first N" — it means fewer than N have applied.
            if pat.pattern.startswith(r"be\s+among"):
                return f"first {n}"
            return f"{n}+"
    return None


def market_check(*, title: str, company: str) -> MarketCheckResult:
    key = os.getenv("TAVILY_API_KEY", "").strip()
    if not key:
        raise MarketCheckError(
            "TAVILY_API_KEY is not set. Add it to your environment to enable market checks."
        )

    query = f'"{title}" "{company}" hiring'
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 5,
                "include_answer": False,
                "include_domains": ["linkedin.com"],
            },
            timeout=30,
        )
    except httpx.HTTPError as exc:
        raise MarketCheckError(f"Tavily request failed: {exc}") from exc

    if r.status_code != 200:
        try:
            msg = r.json().get("error") or r.json().get("detail") or r.text
        except ValueError:
            msg = r.text
        raise MarketCheckError(f"Tavily error {r.status_code}: {str(msg)[:200]}")

    data = r.json()
    results = data.get("results") or []

    # Extract ONLY from the exact-match /jobs/view/ snippet. Other Tavily results are usually
    # different Ashby/Greenhouse roles, and their "4 days ago" / "200+ applicants" hints do
    # NOT belong to this job — mixing them in produces confidently-wrong attribution.
    job_view = next((r for r in results if "/jobs/view/" in (r.get("url") or "")), None)
    fallback = results[0] if results else None
    top = job_view or fallback

    linkedin_url = (top or {}).get("url")
    scoped = (job_view or {}).get("content", "") or ""

    age = _extract_age(scoped)
    applicants = _extract_applicants(scoped)
    reposted = bool(_REPOSTED_RE.search(scoped))
    closed = bool(_CLOSED_RE.search(scoped))

    if not results:
        summary = "Posted: not found on LinkedIn\nApplicants: —"
    elif job_view is None:
        # Have some LinkedIn presence but no canonical job posting — usually a personal
        # post or company page. Report honestly rather than guessing.
        summary = "Posted: no LinkedIn job posting found\nApplicants: —"
    else:
        posted_line = f"Posted: {age or 'unknown'}"
        if reposted:
            posted_line += " (reposted)"
        if closed:
            posted_line += " · no longer accepting"
        applicants_line = f"Applicants: {applicants or 'unknown'}"
        summary = f"{posted_line}\n{applicants_line}"

    return MarketCheckResult(summary=summary, linkedin_url=linkedin_url)
