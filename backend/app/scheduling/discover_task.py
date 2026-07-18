"""Rotating auto-discovery of new Greenhouse job boards.

Cycles through a diverse set of natural-language queries so over the course of a week
or two we cover many industries and stages. Any new board that validates gets added
and immediately synced so its jobs show up in the search table.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select

from app.db import SessionLocal
from app.discovery.source_detection import detect_source
from app.domain.models import Company, JobSource
from app.sync.sync_service import sync_source

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9\-]+)")

# Rotated one-per-run. Diverse across stage, industry, and geography so the crawl
# widens naturally over time. Feel free to edit — the runtime rotates based on the
# day-of-year so any change takes effect immediately.
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
    skipped_too_large: list[str] = field(default_factory=list)  # tokens skipped for job_count > cap
    skipped: str | None = None  # populated when the whole run was skipped (e.g. no API key)


# Skip auto-adding any board bigger than this — the assumption is that giant boards
# (>150 open roles) belong to well-known companies whose jobs cross-post everywhere,
# so they add noise rather than uncovering hidden opportunities. Manual paste/single-add
# is still available if you specifically want a big board.
MAX_AUTO_ADD_JOB_COUNT = 150


def _pick_query() -> str:
    day = datetime.now(timezone.utc).timetuple().tm_yday
    return QUERIES[day % len(QUERIES)]


def _search_via_tavily(query: str) -> tuple[str, str | None]:
    """Query Tavily and return the raw JSON as text so the token regex can pick out URLs.

    Free tier: 1,000 searches/month, no card required. Filters to boards.greenhouse.io
    so we don't burn a call on unrelated results.
    """
    import httpx

    key = os.environ["TAVILY_API_KEY"]
    r = httpx.post(
        "https://api.tavily.com/search",
        json={
            "api_key": key,
            "query": f"{query} careers hiring greenhouse job board",
            "search_depth": "advanced",
            "max_results": 20,
            "include_domains": ["boards.greenhouse.io"],
        },
        timeout=30,
    )
    if r.status_code != 200:
        try:
            msg = r.json().get("error") or r.json().get("detail") or r.text
        except ValueError:
            msg = r.text
        return "", f"Tavily API error ({r.status_code}): {str(msg)[:200]}"
    # We return the full body as a string; the caller extracts tokens with a regex.
    return r.text, None


def _search_via_gemini(query: str) -> tuple[str, str | None]:
    """Try Gemini's google_search grounding. Returns (text_blob, error_reason)."""
    import httpx  # local import so the module imports cleanly at boot

    key = os.environ["GEMINI_API_KEY"]
    prompt = (
        f"Find at least 15 unique URLs of the form boards.greenhouse.io/<token> for "
        f"{query}. Prefer smaller/less-known companies. Return URLs only, one per line."
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
        f"Search the web for `site:boards.greenhouse.io {query}` and return every unique "
        "boards.greenhouse.io/<token> URL you find in the results, one per line, nothing else. "
        "Prefer smaller/less-known companies. Return at least 15 URLs if possible."
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


def run_auto_discover() -> DiscoverStats:
    """One rotation-step of auto-discovery: search, validate, add new boards, sync each.

    Prefers Gemini's google_search grounding (free-tier friendly for the LLM half, though
    grounding itself requires a paid Google Cloud project). Falls back to Anthropic's
    web_search tool if only ANTHROPIC_API_KEY is set. If neither succeeds, records the
    error on the returned stats so the UI can surface it.
    """
    stats = DiscoverStats(query=_pick_query())

    has_tavily = bool(os.getenv("TAVILY_API_KEY", "").strip())
    has_gemini = bool(os.getenv("GEMINI_API_KEY", "").strip())
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY", "").strip())
    if not (has_tavily or has_gemini or has_anthropic):
        stats.skipped = "No search key set (TAVILY_API_KEY, GEMINI_API_KEY, or ANTHROPIC_API_KEY)"
        logger.info("auto-discover skipped — %s", stats.skipped)
        return stats

    logger.info("auto-discover starting query=%r", stats.query)

    # Prefer Tavily (free, no card, purpose-built for web search); fall back to LLM
    # providers with search grounding if Tavily isn't configured or errors out.
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
            "Gemini's Google Search grounding requires a paid Cloud project; "
            "use the paste-mode Discover section on /sources instead."
        )
        logger.info("auto-discover: %s", stats.skipped)
        return stats

    tokens = set(_TOKEN_RE.findall(text_blob))
    stats.tokens_found = len(tokens)
    if not tokens:
        logger.info("auto-discover found no tokens for query=%r", stats.query)
        return stats

    session = SessionLocal()
    try:
        existing = {
            row.source_identifier for row in session.scalars(
                select(JobSource).where(JobSource.provider == "greenhouse")
            )
        }
        new_tokens = tokens - existing
        logger.info(
            "auto-discover found %d tokens (%d new) for query=%r",
            len(tokens), len(new_tokens), stats.query,
        )
    finally:
        session.close()

    # Each add + sync gets its own session so a failure on one doesn't poison the batch.
    for token in new_tokens:
        # Pre-check the board's size before committing to an add + sync. Skip anything
        # bigger than MAX_AUTO_ADD_JOB_COUNT (assumed cross-posted noise from big co's).
        try:
            import httpx
            r = httpx.get(
                f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                timeout=6.0,
            )
            job_count = len(r.json().get("jobs", [])) if r.status_code == 200 else None
        except Exception:  # noqa: BLE001
            job_count = None
        if job_count is None:
            continue  # unreachable board; skip silently
        if job_count > MAX_AUTO_ADD_JOB_COUNT:
            stats.skipped_too_large.append(f"{token} ({job_count})")
            logger.info("auto-discover skipping token=%s size=%d (> %d)", token, job_count, MAX_AUTO_ADD_JOB_COUNT)
            continue

        session = SessionLocal()
        try:
            url = f"https://boards.greenhouse.io/{token}"
            detected = detect_source(url)
            if detected is None:
                continue
            company_name = detected.source_identifier.replace("-", " ").title()
            company = session.scalar(select(Company).where(Company.name == company_name))
            if company is None:
                company = Company(name=company_name)
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
            logger.warning("auto-discover add token=%s failed: %s", token, exc)
            session.close()
            continue

        # Sync in a fresh session so the source row is committed and visible.
        session = SessionLocal()
        try:
            result = sync_source(session, source_id)
            stats.new_boards_added += 1
            stats.jobs_added += result.jobs_added
            stats.added_tokens.append(token)
            logger.info(
                "auto-discover added token=%s jobs_added=%s",
                token, result.jobs_added,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-discover sync token=%s failed: %s", token, exc)
        finally:
            session.close()

    logger.info(
        "auto-discover finished query=%r new_boards_added=%d jobs_added=%d",
        stats.query, stats.new_boards_added, stats.jobs_added,
    )
    return stats
