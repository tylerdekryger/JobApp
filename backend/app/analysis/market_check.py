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
from urllib.parse import quote_plus

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
_STOPWORDS = {
    "the", "a", "an", "of", "at", "in", "on", "for", "to", "and", "or",
    "with", "as", "by", "sr", "jr", "senior", "junior",
}
_LINKEDIN_SLUG_RE = re.compile(r"/jobs/view/([a-z0-9\-]+)-\d+", re.IGNORECASE)


def _significant_words(text: str) -> set[str]:
    """Return content words (lowercase, ≥3 chars, not stopwords) from a string."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _slug_match_score(url: str, title: str, company: str) -> float:
    """0..1 Jaccard similarity between the slug's title-portion and the target title.

    Jaccard = |intersection| / |union|, computed over the significant (non-stopword,
    non-company) words. Using recall-only overlap accepts slugs that add extra topics
    the target doesn't have (e.g. "manager-customer-lifecycle-marketing-at-benepass"
    scores 2/3=0.67 for target "Manager, Customer Success" — the "lifecycle" and
    "marketing" extras should penalize it). Jaccard drops that to 2/5=0.4.

    Company must appear in the slug — else score is 0 (protects against picking a
    same-title role at a different company).
    """
    m = _LINKEDIN_SLUG_RE.search(url)
    if not m:
        return 0.0
    slug_all = set(re.findall(r"[a-z0-9]+", m.group(1).lower()))
    title_words = _significant_words(title)
    company_words = _significant_words(company)
    if not title_words:
        return 0.0
    if company_words and not (company_words & slug_all):
        return 0.0
    # Compare only the "role" portion of the slug — strip the company and stopwords.
    slug_role = {w for w in slug_all if w not in company_words and w not in _STOPWORDS and len(w) > 2}
    if not slug_role:
        return 0.0
    intersection = title_words & slug_role
    union = title_words | slug_role
    return len(intersection) / len(union) if union else 0.0


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

    # Punctuation in the title doesn't survive LinkedIn's slugification, and quoting the
    # whole phrase tanks recall. Send the cleaned title + quoted company + "hiring" instead.
    clean_title = re.sub(r"[^\w\s]", " ", title)
    query = f'{clean_title} "{company}" hiring'
    try:
        r = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": key,
                "query": query,
                "search_depth": "advanced",
                "max_results": 10,
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

    # Score every /jobs/view/ URL by how well its slug matches the target title+company.
    # Only accept the best match if it clears a threshold — otherwise Tavily surfaced a
    # different-role-same-company posting (or the wrong company entirely), which we should
    # NOT pin to this job. Threshold of 0.5 = at least half the significant title words
    # must appear in the URL slug.
    view_results = [r for r in results if "/jobs/view/" in (r.get("url") or "")]
    scored = sorted(
        ((r, _slug_match_score(r.get("url") or "", title, company)) for r in view_results),
        key=lambda p: p[1], reverse=True,
    )
    best_view, best_score = (scored[0] if scored else (None, 0.0))
    accepted = best_view if best_score >= 0.5 else None

    # Only surface a LinkedIn URL when the slug is a real match for THIS job. If nothing
    # scores above threshold, give the user a LinkedIn search URL instead of a plausible-
    # looking but wrong /jobs/view/ link.
    if accepted is not None:
        linkedin_url = accepted.get("url")
    else:
        search_terms = quote_plus(f"{title} {company}")
        linkedin_url = f"https://www.linkedin.com/jobs/search/?keywords={search_terms}"
    scoped = (accepted or {}).get("content", "") or ""

    age = _extract_age(scoped)
    applicants = _extract_applicants(scoped)
    reposted = bool(_REPOSTED_RE.search(scoped))
    closed = bool(_CLOSED_RE.search(scoped))

    if not results:
        summary = "Posted: not found on LinkedIn\nApplicants: —"
    elif accepted is None:
        # We got LinkedIn hits but none of the /jobs/view/ URLs match this title strongly
        # enough. Rather than mis-attribute a different Benepass/Ashby role, say so honestly.
        summary = "Posted: no matching LinkedIn posting\nApplicants: —"
    else:
        posted_line = f"Posted: {age or 'unknown'}"
        if reposted:
            posted_line += " (reposted)"
        if closed:
            posted_line += " · no longer accepting"
        applicants_line = f"Applicants: {applicants or 'unknown'}"
        summary = f"{posted_line}\n{applicants_line}"

    return MarketCheckResult(summary=summary, linkedin_url=linkedin_url)
