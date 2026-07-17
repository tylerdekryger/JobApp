from datetime import datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import Job
from app.providers.base import NormalizedJob


class UpsertOutcome(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    UNCHANGED = "unchanged"


def upsert_job(
    session: Session,
    *,
    company_id: int,
    job_source_id: int,
    normalized: NormalizedJob,
    content_hash: str,
    now: datetime,
) -> tuple[Job, UpsertOutcome]:
    """Level-1 dedupe (spec §15): exact match on (job_source_id, external_job_id)."""
    existing = session.scalar(
        select(Job).where(
            Job.job_source_id == job_source_id,
            Job.external_job_id == normalized.source_job_id,
        )
    )

    if existing is None:
        job = Job(
            company_id=company_id,
            job_source_id=job_source_id,
            external_job_id=normalized.source_job_id,
            canonical_url=normalized.canonical_url,
            title=normalized.title,
            description=normalized.description,
            location=normalized.location,
            remote_type=normalized.remote_type,
            employment_type=normalized.employment_type,
            department=normalized.department,
            salary_min=normalized.salary_min,
            salary_max=normalized.salary_max,
            salary_currency=normalized.salary_currency,
            posted_at=normalized.posted_at,
            first_seen_at=now,
            last_seen_at=now,
            last_content_change_at=now,
            status="active",
            content_hash=content_hash,
        )
        session.add(job)
        return job, UpsertOutcome.ADDED

    existing.last_seen_at = now
    existing.status = "active"

    if existing.content_hash != content_hash:
        existing.canonical_url = normalized.canonical_url
        existing.title = normalized.title
        existing.description = normalized.description
        existing.location = normalized.location
        existing.remote_type = normalized.remote_type
        existing.employment_type = normalized.employment_type
        existing.department = normalized.department
        existing.salary_min = normalized.salary_min
        existing.salary_max = normalized.salary_max
        existing.salary_currency = normalized.salary_currency
        existing.posted_at = normalized.posted_at
        existing.content_hash = content_hash
        existing.last_content_change_at = now
        return existing, UpsertOutcome.UPDATED

    return existing, UpsertOutcome.UNCHANGED
