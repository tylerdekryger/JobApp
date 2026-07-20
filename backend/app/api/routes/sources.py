from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.discovery.source_detection import detect_source
from app.domain.models import Company, Job, JobSource
from app.domain.schemas import (
    SourceCreateRequest,
    SourceListResponse,
    SourceResponse,
    SourceSummary,
    SyncResultResponse,
)
from app.sync.sync_service import sync_source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
def list_sources(db: Session = Depends(get_db)) -> SourceListResponse:
    active_job_count = func.count(Job.id).filter(Job.status == "active")
    rows = db.execute(
        select(
            JobSource.id,
            JobSource.company_id,
            Company.name.label("company_name"),
            JobSource.provider,
            JobSource.source_url,
            JobSource.source_identifier,
            JobSource.status,
            JobSource.last_successful_sync,
            JobSource.last_attempted_sync,
            JobSource.last_error,
            active_job_count.label("active_job_count"),
        )
        .join(Company, Company.id == JobSource.company_id)
        .outerjoin(Job, Job.job_source_id == JobSource.id)
        .group_by(JobSource.id, Company.name)
        .order_by(Company.name)
    ).all()

    items = [SourceSummary(**dict(row._mapping)) for row in rows]
    return SourceListResponse(items=items, total=len(items))


@router.post("", response_model=SourceResponse, status_code=201)
def create_source(payload: SourceCreateRequest, db: Session = Depends(get_db)) -> JobSource:
    detected = detect_source(payload.url)
    if detected is None:
        raise HTTPException(
            status_code=422, detail=f"Could not detect a supported ATS provider for URL: {payload.url}"
        )

    existing_source = db.scalar(
        select(JobSource).where(
            JobSource.provider == detected.provider,
            JobSource.source_identifier == detected.source_identifier,
        )
    )
    if existing_source is not None:
        return existing_source

    # Workday's source_identifier is a composite "tenant||host||site". Use just the
    # tenant part for a human display name; other providers already have a bare token.
    display_token = detected.source_identifier
    if detected.provider == "workday" and "||" in display_token:
        display_token = display_token.split("||", 1)[0]
    company_name = payload.company_name or display_token.replace("-", " ").replace("_", " ").title()
    company = db.scalar(select(Company).where(Company.name == company_name))
    if company is None:
        company = Company(name=company_name)
        db.add(company)
        db.flush()

    source = JobSource(
        company_id=company.id,
        provider=detected.provider,
        source_url=detected.source_url,
        source_identifier=detected.source_identifier,
        status="pending",
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.post("/{source_id}/sync", response_model=SyncResultResponse)
def trigger_sync(source_id: int, db: Session = Depends(get_db)) -> SyncResultResponse:
    if db.get(JobSource, source_id) is None:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        result = sync_source(db, source_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Sync failed: {exc}") from exc

    return SyncResultResponse(
        source_id=result.source_id,
        jobs_found=result.jobs_found,
        jobs_added=result.jobs_added,
        jobs_updated=result.jobs_updated,
        jobs_removed=result.jobs_removed,
        duration_seconds=result.duration_seconds,
    )


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)) -> None:
    source = db.scalar(select(JobSource).options(joinedload(JobSource.company)).where(JobSource.id == source_id))
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    company_id = source.company_id
    db.execute(delete(Job).where(Job.job_source_id == source_id))
    db.delete(source)
    db.flush()

    # If the company has no remaining sources or jobs, remove it too — keeps the sources page clean.
    remaining_sources = db.scalar(select(func.count()).select_from(JobSource).where(JobSource.company_id == company_id))
    remaining_jobs = db.scalar(select(func.count()).select_from(Job).where(Job.company_id == company_id))
    if not remaining_sources and not remaining_jobs:
        db.execute(delete(Company).where(Company.id == company_id))

    db.commit()
