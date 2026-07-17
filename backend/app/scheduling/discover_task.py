"""Rotating auto-discovery of new Greenhouse job boards.

Cycles through a diverse set of natural-language queries so over the course of a week
or two we cover many industries and stages. Any new board that validates gets added
and immediately synced so its jobs show up in the search table.
"""
from __future__ import annotations

import logging
import os
import re
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


def _pick_query() -> str:
    day = datetime.now(timezone.utc).timetuple().tm_yday
    return QUERIES[day % len(QUERIES)]


def run_auto_discover() -> None:
    """One rotation-step of auto-discovery: search, validate, add new boards, sync each."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        logger.info("auto-discover skipped — ANTHROPIC_API_KEY not set")
        return

    query = _pick_query()
    logger.info("auto-discover starting query=%r", query)

    try:
        from anthropic import Anthropic, APIError
    except ImportError:
        logger.warning("anthropic SDK not installed — skipping auto-discover")
        return

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
        logger.warning("auto-discover Anthropic error: %s", exc)
        return

    text_blob = "\n".join(
        getattr(block, "text", "") for block in msg.content if getattr(block, "type", "") == "text"
    )
    tokens = set(_TOKEN_RE.findall(text_blob))
    if not tokens:
        logger.info("auto-discover found no tokens for query=%r", query)
        return

    added = 0
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
            len(tokens), len(new_tokens), query,
        )
    finally:
        session.close()

    # Each add + sync gets its own session so a failure on one doesn't poison the batch.
    for token in new_tokens:
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
            added += 1
            logger.info(
                "auto-discover added token=%s jobs_added=%s",
                token, result.jobs_added,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto-discover sync token=%s failed: %s", token, exc)
        finally:
            session.close()

    logger.info("auto-discover finished query=%r new_boards_added=%d", query, added)
