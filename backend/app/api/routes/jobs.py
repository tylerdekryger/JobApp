from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import Job
from app.domain.schemas import JobListResponse, JobResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=JobListResponse)
def list_jobs(
    company_id: int | None = None,
    source_id: int | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200, gt=0),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> JobListResponse:
    filters = []
    if company_id is not None:
        filters.append(Job.company_id == company_id)
    if source_id is not None:
        filters.append(Job.job_source_id == source_id)
    if status is not None:
        filters.append(Job.status == status)

    total = db.scalar(select(func.count()).select_from(Job).where(*filters)) or 0
    jobs = db.scalars(
        select(Job).where(*filters).order_by(Job.first_seen_at.desc()).limit(limit).offset(offset)
    ).all()

    return JobListResponse(
        items=[JobResponse.model_validate(job) for job in jobs],
        limit=limit,
        offset=offset,
        total=total,
    )
