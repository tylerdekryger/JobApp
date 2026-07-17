"""In-process background scheduler.

Runs two recurring jobs so the app stays fresh without any user action:

- ``auto_sync_all_sources``  — re-syncs every registered JobSource on a short cadence
  (default 60 minutes) so newly-posted jobs at existing companies surface quickly.
- ``auto_discover_new_boards`` — runs a rotating natural-language query against Claude
  web search once per interval (default 24 h) to find brand-new Greenhouse boards and
  auto-add + auto-sync any that pass validation. Requires ``ANTHROPIC_API_KEY``; skipped
  silently otherwise.

Both cadences are configurable via env vars and each job runs *sequentially* to avoid
hammering Greenhouse or the Anthropic API. The scheduler starts on FastAPI's startup
event and stops on shutdown.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.db import SessionLocal
from app.domain.models import JobSource
from app.scheduling.discover_task import run_auto_discover
from app.sync.sync_service import sync_source

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
        return v if v > 0 else default
    except ValueError:
        return default


def auto_sync_all_sources() -> None:
    """Sync every JobSource sequentially. Errors on one source don't halt the rest."""
    session = SessionLocal()
    try:
        source_ids = [row.id for row in session.query(JobSource).all()]
    finally:
        session.close()

    logger.info("auto-sync starting for %d sources", len(source_ids))
    for source_id in source_ids:
        session = SessionLocal()
        try:
            result = sync_source(session, source_id)
            logger.info(
                "auto-sync source=%s added=%s updated=%s removed=%s duration=%.1fs",
                source_id, result.jobs_added, result.jobs_updated, result.jobs_removed,
                result.duration_seconds,
            )
        except Exception as exc:  # noqa: BLE001 — keep the loop alive
            logger.warning("auto-sync source=%s failed: %s", source_id, exc)
        finally:
            session.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return

    sync_minutes = _int_env("AUTO_SYNC_INTERVAL_MINUTES", 60)
    discover_hours = _int_env("AUTO_DISCOVER_INTERVAL_HOURS", 24)
    disabled = os.getenv("DISABLE_SCHEDULER", "").strip().lower() in {"1", "true", "yes"}

    if disabled:
        logger.info("scheduler disabled via DISABLE_SCHEDULER env var")
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        auto_sync_all_sources,
        "interval",
        minutes=sync_minutes,
        id="auto_sync",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        run_auto_discover,
        "interval",
        hours=discover_hours,
        id="auto_discover",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "scheduler started — auto-sync every %d min, auto-discover every %d h",
        sync_minutes, discover_hours,
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
