from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deduplication.dedupe import UpsertOutcome, upsert_job
from app.domain.models import Job, JobSource
from app.logging import get_logger
from app.normalization.content_hash import compute_content_hash
from app.normalization.text import detect_boilerplate_prefix
from app.providers.registry import get_provider

logger = get_logger(__name__)

# Skip jobs older than this at ingest time so the DB doesn't accumulate stale roles.
# Postings without a posted_at date are kept (we have no signal to filter on).
MAX_JOB_AGE = timedelta(days=30)


@dataclass
class SyncResult:
    source_id: int
    jobs_found: int
    jobs_added: int
    jobs_updated: int
    jobs_removed: int
    duration_seconds: float


def sync_source(session: Session, source_id: int) -> SyncResult:
    """Fetch -> normalize -> content-hash -> dedupe/upsert -> close missing (spec §15/§16), idempotently."""
    source = session.get(JobSource, source_id)
    if source is None:
        raise ValueError(f"JobSource {source_id} not found")

    started_at = datetime.now(timezone.utc)
    source.last_attempted_sync = started_at

    try:
        provider = get_provider(source.provider)
        raw_jobs = provider.fetch_jobs(source.source_identifier)
    except Exception as exc:
        source.last_error = str(exc)
        session.commit()
        logger.error("sync failed source_id=%s provider=%s error=%s", source.id, source.provider, exc)
        raise

    seen_external_ids: set[str] = set()
    added = updated = 0
    age_cutoff = started_at - MAX_JOB_AGE

    for raw_job in raw_jobs:
        normalized = provider.normalize(raw_job, source.company.name)
        # Skip jobs the source itself reports as older than MAX_JOB_AGE. Jobs whose posted_at
        # can't be parsed are kept — better to include-with-unknown-date than drop silently.
        if normalized.posted_at is not None and normalized.posted_at < age_cutoff:
            continue
        seen_external_ids.add(normalized.source_job_id)
        content_hash = compute_content_hash(normalized)
        _, outcome = upsert_job(
            session,
            company_id=source.company_id,
            job_source_id=source.id,
            normalized=normalized,
            content_hash=content_hash,
            now=started_at,
        )
        if outcome is UpsertOutcome.ADDED:
            added += 1
        elif outcome is UpsertOutcome.UPDATED:
            updated += 1

    removed = _close_missing_jobs(session, source_id=source.id, seen_external_ids=seen_external_ids)

    # Detect per-source description boilerplate now that we have all active descriptions in hand.
    # Stored on JobSource and stripped at display time (raw description stays intact on Job).
    active_descriptions = session.scalars(
        select(Job.description).where(Job.job_source_id == source.id, Job.status == "active")
    ).all()
    source.description_boilerplate_prefix = detect_boilerplate_prefix(list(active_descriptions)) or None

    source.last_successful_sync = started_at
    source.last_error = None
    source.status = "active"
    session.commit()

    duration_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
    result = SyncResult(
        source_id=source.id,
        jobs_found=len(raw_jobs),
        jobs_added=added,
        jobs_updated=updated,
        jobs_removed=removed,
        duration_seconds=duration_seconds,
    )
    logger.info(
        "sync completed source_id=%s provider=%s jobs_found=%s jobs_added=%s jobs_updated=%s "
        "jobs_removed=%s duration=%.2fs",
        source.id,
        source.provider,
        result.jobs_found,
        result.jobs_added,
        result.jobs_updated,
        result.jobs_removed,
        result.duration_seconds,
    )
    return result


def _close_missing_jobs(session: Session, *, source_id: int, seen_external_ids: set[str]) -> int:
    active_jobs = session.scalars(select(Job).where(Job.job_source_id == source_id, Job.status == "active")).all()
    closed = 0
    for job in active_jobs:
        if job.external_job_id not in seen_external_ids:
            job.status = "closed"
            closed += 1
    return closed
