"""In-process background scheduler.

Runs two recurring jobs so the app stays fresh without any user action:

- ``auto_sync_all_sources``  — re-syncs every registered JobSource on a short cadence
  (default 60 minutes) so newly-posted jobs at existing companies surface quickly.
- ``auto_discover_new_boards`` — runs a rotating natural-language query against Claude
  web search to find brand-new Greenhouse boards and auto-add + auto-sync any that pass
  validation. Fires on a business-hours cron: Monday–Friday, 08:00–18:00 America/New_York,
  every 2 hours (6 runs/day, 30 runs/week). Requires ``ANTHROPIC_API_KEY``; skipped
  silently otherwise.

Each job runs sequentially with ``max_instances=1`` to avoid hammering Greenhouse or the
Anthropic API. The scheduler starts on FastAPI's startup event and stops on shutdown.
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import SessionLocal
from app.domain.models import JobSource
from app.scheduling.discover_task import run_auto_discover
from app.sync.sync_service import sync_source

# The digest send is a light wrapper so the scheduler doesn't blow up when SMTP isn't
# configured — it should just log and skip.
def _run_digest_safe() -> None:
    try:
        from app.digest.service import DigestError, send_daily_digest
        try:
            result = send_daily_digest()
            logger.info(
                "daily-digest job ran presets=%d matches=%d skipped=%s",
                result.presets_run, result.total_matches, result.skipped,
            )
        except DigestError as exc:
            logger.warning("daily-digest skipped: %s", exc)
    except Exception:  # noqa: BLE001 — never let the scheduler die on this
        logger.exception("daily-digest crashed unexpectedly")

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
    # Weekly discovery cron: Monday 08:00 ET. Previously ran 30x/week which burned
    # through Tavily's 1,000/month free tier. One run/week (~4/month) leaves plenty
    # of budget for user-triggered "Market check" clicks.
    discover_trigger = CronTrigger(
        day_of_week="mon",
        hour=8,
        minute=0,
        timezone="America/New_York",
    )
    _scheduler.add_job(
        run_auto_discover,
        discover_trigger,
        id="auto_discover",
        max_instances=1,
        coalesce=True,
    )

    # Daily email digest — Mon–Fri at the configured hour (default 8am ET).
    digest_hour = _int_env("DIGEST_HOUR_ET", 8)
    digest_trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=digest_hour,
        minute=0,
        timezone="America/New_York",
    )
    _scheduler.add_job(
        _run_digest_safe,
        digest_trigger,
        id="daily_digest",
        max_instances=1,
        coalesce=True,
    )

    logger.info(
        "scheduler started — auto-sync every %d min; auto-discover Mon 08:00 ET (weekly); "
        "daily-digest Mon-Fri %02d:00 ET",
        sync_minutes, digest_hour,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
