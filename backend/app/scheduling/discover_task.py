"""Rotating auto-discovery of new ATS job boards (Greenhouse + Ashby).

Cycles through a diverse set of natural-language queries so over the course of a week
or two we cover many industries and stages. Any new board that validates gets added
and immediately synced so its jobs show up in the search table.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.discovery.candidate_extraction import (
    extract_tokens,
    validate_candidates,
)
from app.discovery.source_detection import detect_source
from app.domain.models import Company, JobSource
from app.sync.sync_service import sync_source

logger = logging.getLogger(__name__)

# Rotated one-per-run. Diverse across stage, industry, and geography so the crawl
# widens naturally over time.
QUERIES = [
    "climate energy startups series A",
    "healthtech remote series B",
    "developer tools infrastructure startup",
    "AI machine learning startup hiring",
    "fintech payments startup",
    "biotech pharmaceutical seed",
    "consumer product startup remote",
    "cybersecurity startup remote",
    "edtech education startup",
    "marketplace platform startup",
    "media publishing digital startup",
    "climate carbon removal startup",
    "quantitative finance trading",
    "agtech food startup remote",
    "robotics automation startup",
    "logistics supply chain startup",
    "gaming games studio remote",
    "creator economy startup",
    "productivity SaaS remote",
    "space aerospace startup",
    "nonprofit tech hiring",
    "govtech civic tech startup",
    "insurance insurtech startup",
    "hardware devices startup",
    "cryptocurrency blockchain startup",
    "seed stage YC company hiring",
    "series B growth startup remote",
    "boutique consulting agency hiring",
]


@dataclass
class DiscoverStats:
    query: str
    tokens_found: int = 0
    new_boards_added: int = 0
    jobs_added: int = 0
    added_tokens: list[str] = field(default_factory=list)
    skipped_too_large: list[str] = field(default_factory=list)
    skipped: str | None = None


# Skip auto-adding any board bigger than this. Big boards belong to well-known
# companies whose jobs cross-post everywhere, which adds noise. Manual paste/single-add
# is still available if a specific big board is wanted.
MAX_AUTO_ADD_JOB_COUNT = 150

# Domains we know how to consume; Tavily narrows to these to avoid burning a query on
# unrelated results.
SEARCH_INCLUDE_DOMAINS = [
    "boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "jobs.lever.co",
    "jobs.smartrecruiters.com",
    "breezy.hr",
]


def _pick_query() -> str:
    day = datetime.now(timezone.utc).timetuple().tm_yday
    return QUERIES[day % len(QUERIES)]


def _search_via_tavily(query: str) -> tuple[str, str | None]:
    """Query Tavily; return the raw JSON as text so the extractor can pull URLs."""
    import httpx

    key = os.environ["TAVILY_API_KEY"]
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": key,
            "query": f"{query} careers hiring job board",
            "search_depth": "advanced",
            "max_results": 20,
            "include_domains": SEARCH_INCLUDE_DOMAINS,
        },
        timeout=30,
    )
    if r.status_code != 200:
        try:
            msg = r.json().get("error") or r.json().get("detail") or r.text
        except ValueError:
            msg = r.text
        return "", f"Tavily API error ({r.status_code}): {str(msg)[:200]}"
    return r.text, None


def _search_via_gemini(query: str) -> tuple[str, str | None]:
    """Try Gemini's google_search grounding. Returns (text_blob, error_reason)."""
    import httpx

    key = os.environ["GEMINI_API_KEY"]
    prompt = (
        f"Find at least 15 unique career-board URLs for {query}. Return URLs only, one per "
        "line, matching any of: `boards.greenhouse.io/<token>` (Greenhouse), "
        "`jobs.ashbyhq.com/<orgId>` (Ashby), `jobs.lever.co/<slug>` (Lever), "
        "`jobs.smartrecruiters.com/<companyId>` (SmartRecruiters), or "
        "`<company>.breezy.hr` (BreezyHR). Prefer smaller/less-known companies."
    )
    r = httpx.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent",
        headers={"X-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
        },
        timeout=60,
    )
    if r.status_code != 200:
        try:
            msg = r.json().get("error", {}).get("message", r.text)
        except ValueError:
            msg = r.text
        return "", f"Gemini API error ({r.status_code}): {msg[:200]}"
    body = r.json()
    parts = body.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    text = "\n".join(p.get("text", "") for p in parts if "text" in p)
    return text, None


def _search_via_anthropic(query: str) -> tuple[str, str | None]:
    """Try Claude's web_search tool. Returns (text_blob, error_reason)."""
    try:
        from anthropic import Anthropic, APIError
    except ImportError:
        return "", "anthropic SDK not installed"

    client = Anthropic()
    prompt = (
        f"Search the web for career-board URLs matching `{query}`. Return every unique URL "
        "you find matching `boards.greenhouse.io/<token>`, `jobs.ashbyhq.com/<orgId>`, "
        "`jobs.lever.co/<slug>`, `jobs.smartrecruiters.com/<companyId>`, or "
        "`<company>.breezy.hr`. One per line, nothing else. Prefer smaller/less-known "
        "companies. Return at least 15 URLs if possible."
    )
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}],
        )
    except APIError as exc:
        return "", f"Anthropic API error: {exc}"

    text = "\n".join(
        getattr(block, "text", "") for block in msg.content if getattr(block, "type", "") == "text"
    )
    return text, None


def _existing_by_provider() -> dict[str, set[str]]:
    session = SessionLocal()
    try:
        out: dict[str, set[str]] = {}
        for row in session.scalars(select(JobSource)):
            out.setdefault(row.provider, set()).add(row.source_identifier)
        return out
    finally:
        session.close()


def _register_and_sync(provider: str, token: str, source_url: str, display_name: str) -> tuple[int, bool]:
    """Create a JobSource + run one sync. Returns (jobs_added, ok)."""
    session = SessionLocal()
    try:
        detected = detect_source(source_url)
        if detected is None:
            return 0, False
        company = session.scalar(select(Company).where(Company.name == display_name))
        if company is None:
            company = Company(name=display_name)
            session.add(company)
            session.flush()
        source = JobSource(
            company_id=company.id,
            provider=detected.provider,
            source_url=detected.source_url,
            source_identifier=detected.source_identifier,
            status="pending",
        )
        session.add(source)
        session.commit()
        source_id = source.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto-discover add %s/%s failed: %s", provider, token, exc)
        session.close()
        return 0, False

    session = SessionLocal()
    try:
        result = sync_source(session, source_id)
        return result.jobs_added, True
    except Exception as exc:  # noqa: BLE001
        logger.warning("auto-discover sync %s/%s failed: %s", provider, token, exc)
        return 0, False
    finally:
        session.close()


def run_auto_discover() -> DiscoverStats:
    """One rotation-step: search, validate, filter by size, add new boards, sync each."""
    stats = DiscoverStats(query=_pick_query())

    has_tavily = bool(os.getenv("TAVILY_API_KEY", "").strip())
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if not (has_tavily or has_gemini or has_anthropic):
        stats.skipped = "No search key set (TAVILY_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY)"
        logger.info("auto-discover skipped — %s", stats.skipped)
        return stats

    logger.info("auto-discover starting query=%r", stats.query)

    providers: list[tuple[str, callable]] = []
    if has_tavily:
        providers.append(("tavily", _search_via_tavily))
    if has_gemini:
        providers.append(("gemini", _search_via_gemini))
    if has_anthropic:
        providers.append(("anthropic", _search_via_anthropic))

    text_blob = ""
    last_error: str | None = None
    for name, fn in providers:
        text_blob, err = fn(stats.query)
        if err is None and text_blob:
            logger.info("auto-discover search via %s succeeded", name)
            break
        last_error = f"{name}: {err or 'empty response'}"
        logger.info("auto-discover search via %s failed — %s", name, err)

    if not text_blob:
        stats.skipped = (
            f"web search unavailable ({last_error}). "
            "Use the paste-mode Discover section on /sources instead."
        )
        logger.info("auto-discover: %s", stats.skipped)
        return stats

    matches = extract_tokens(text_blob)
    stats.tokens_found = len(matches)
    if not matches:
        logger.info("auto-discover found no tokens for query=%r", stats.query)
        return stats

    existing = _existing_by_provider()
    new_matches = [m for m in matches if m.token not in existing.get(m.provider, set())]
    logger.info(
        "auto-discover found %d tokens (%d new) for query=%r",
        len(matches), len(new_matches), stats.query,
    )

    # Validate size + name for each new candidate in parallel; discard anything too large.
    candidates = validate_candidates(set(new_matches))
    for cand in candidates:
        if cand.job_count > MAX_AUTO_ADD_JOB_COUNT:
            stats.skipped_too_large.append(f"{cand.token} ({cand.job_count})")
            logger.info(
                "auto-discover skipping %s/%s size=%d (> %d)",
                cand.provider, cand.token, cand.job_count, MAX_AUTO_ADD_JOB_COUNT,
            )
            continue

        jobs_added, ok = _register_and_sync(cand.provider, cand.token, cand.source_url, cand.name)
        if ok:
            stats.new_boards_added += 1
            stats.jobs_added += jobs_added
            stats.added_tokens.append(f"{cand.provider}:{cand.token}")
            logger.info(
                "auto-discover added %s/%s jobs_added=%s",
                cand.provider, cand.token, jobs_added,
            )

    logger.info(
        "auto-discover finished query=%r new_boards_added=%d jobs_added=%d",
        stats.query, stats.new_boards_added, stats.jobs_added,
    )
    return stats
