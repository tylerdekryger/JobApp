from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.domain.models import Company, Job
from app.domain.schemas import FacetsResponse, FacetValue, JobListResponse, JobResponse
from app.normalization.text import strip_boilerplate

router = APIRouter(prefix="/jobs", tags=["jobs"])


@dataclass
class JobFilters:
    q: str | None
    location: str | None
    department: str | None
    remote_type: str | None
    company_id: int | None
    source_id: int | None
    status: str | None
    posted_since_days: int | None

    def build_conditions(self) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = []
        if self.company_id is not None:
            conditions.append(Job.company_id == self.company_id)
        if self.source_id is not None:
            conditions.append(Job.job_source_id == self.source_id)
        if self.status is not None:
            conditions.append(Job.status == self.status)
        if self.location is not None:
            conditions.append(Job.location.ilike(f"%{self.location}%"))
        if self.department is not None:
            conditions.append(Job.department == self.department)
        if self.remote_type is not None:
            conditions.append(Job.remote_type == self.remote_type)
        if self.posted_since_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.posted_since_days)
            conditions.append(Job.first_seen_at >= cutoff)
        if self.q:
            pattern = f"%{self.q}%"
            conditions.append(
                or_(Job.title.ilike(pattern), Job.description.ilike(pattern), Company.name.ilike(pattern))
            )
        return conditions


def _job_to_response(job: Job) -> JobResponse:
    boilerplate = job.job_source.description_boilerplate_prefix if job.job_source else None
    return JobResponse(
        id=job.id,
        company_id=job.company_id,
        company_name=job.company.name if job.company else None,
        job_source_id=job.job_source_id,
        external_job_id=job.external_job_id,
        canonical_url=job.canonical_url,
        title=job.title,
        description=job.description,
        description_clean=strip_boilerplate(job.description, boilerplate or ""),
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
    department: str | None = Query(default=None, description="Exact match on department"),
    remote_type: str | None = Query(default=None, description="Filter by remote/hybrid/onsite/unknown"),
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
    stmt = (
        select(Job)
        .join(Company, Company.id == Job.company_id)
        .options(joinedload(Job.company), joinedload(Job.job_source))
    )
    count_stmt = select(func.count()).select_from(Job).join(Company, Company.id == Job.company_id)

    filters = JobFilters(
        q=q, location=location, department=department, remote_type=remote_type,
        company_id=company_id, source_id=source_id, status=status,
        posted_since_days=posted_since_days,
    )
    for condition in filters.build_conditions():
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


@router.get("/facets", response_model=FacetsResponse)
def get_facets(
    q: str | None = None,
    location: str | None = None,
    department: str | None = None,
    remote_type: str | None = None,
    company_id: int | None = None,
    source_id: int | None = None,
    status: str | None = "active",
    posted_since_days: int | None = Query(default=None, gt=0, le=365),
    limit: int = Query(default=15, le=50, gt=0),
    db: Session = Depends(get_db),
) -> FacetsResponse:
    filters = JobFilters(
        q=q, location=location, department=department, remote_type=remote_type,
        company_id=company_id, source_id=source_id, status=status,
        posted_since_days=posted_since_days,
    )

    def top_values(column: ColumnElement[str]) -> list[FacetValue]:
        stmt = (
            select(column.label("value"), func.count(Job.id).label("count"))
            .select_from(Job)
            .join(Company, Company.id == Job.company_id)
            .where(column.is_not(None))
            .group_by(column)
            .order_by(func.count(Job.id).desc())
            .limit(limit)
        )
        for cond in filters.build_conditions():
            stmt = stmt.where(cond)
        return [FacetValue(value=row.value, count=row.count) for row in db.execute(stmt).all()]

    return FacetsResponse(
        departments=top_values(Job.department),
        locations=top_values(Job.location),
        companies=top_values(Company.name),
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobResponse:
    job = db.scalar(
        select(Job)
        .options(joinedload(Job.company), joinedload(Job.job_source))
        .where(Job.id == job_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job)
