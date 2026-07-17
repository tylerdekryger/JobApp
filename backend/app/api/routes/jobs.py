from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.domain.models import Company, Job
from app.domain.schemas import JobListResponse, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_to_response(job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        company_id=job.company_id,
        company_name=job.company.name if job.company else None,
        job_source_id=job.job_source_id,
        external_job_id=job.external_job_id,
        canonical_url=job.canonical_url,
        title=job.title,
        description=job.description,
        location=job.location,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        department=job.department,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        posted_at=job.posted_at,
        first_seen_at=job.first_seen_at,
        last_seen_at=job.last_seen_at,
        last_content_change_at=job.last_content_change_at,
        status=job.status,
    )


@router.get("", response_model=JobListResponse)
def list_jobs(
    q: str | None = Query(default=None, description="Keyword search over title, description, company name"),
    location: str | None = Query(default=None, description="Substring match against the job location"),
    company_id: int | None = None,
    source_id: int | None = None,
    status: str | None = "active",
    posted_since_days: int | None = Query(
        default=None, gt=0, le=365, description="Only jobs first seen within the last N days"
    ),
    limit: int = Query(default=25, le=200, gt=0),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobListResponse:
    stmt = select(Job).join(Company, Company.id == Job.company_id).options(joinedload(Job.company))
    count_stmt = select(func.count()).select_from(Job).join(Company, Company.id == Job.company_id)

    conditions = []
    if company_id is not None:
        conditions.append(Job.company_id == company_id)
    if source_id is not None:
        conditions.append(Job.job_source_id == source_id)
    if status is not None:
        conditions.append(Job.status == status)
    if location is not None:
        conditions.append(Job.location.ilike(f"%{location}%"))
    if posted_since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=posted_since_days)
        conditions.append(Job.first_seen_at >= cutoff)
    if q:
        pattern = f"%{q}%"
        conditions.append(
            or_(Job.title.ilike(pattern), Job.description.ilike(pattern), Company.name.ilike(pattern))
        )

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    jobs = db.scalars(stmt.order_by(Job.first_seen_at.desc()).limit(limit).offset(offset)).unique().all()

    return JobListResponse(
        items=[_job_to_response(job) for job in jobs],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    job = db.scalar(select(Job).options(joinedload(Job.company)).where(Job.id == job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)
