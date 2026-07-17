from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.discovery.source_detection import detect_source
from app.domain.models import Company, JobSource
from app.domain.schemas import SourceCreateRequest, SourceResponse, SyncTriggerResponse

router = APIRouter(prefix="/sources", tags=["sources"])


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

    company_name = payload.company_name or detected.source_identifier.replace("-", " ").title()
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


@router.post("/{source_id}/sync", response_model=SyncTriggerResponse, status_code=202)
def trigger_sync(source_id: int, db: Session = Depends(get_db)) -> SyncTriggerResponse:
    source = db.get(JobSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")

    from workers.tasks import sync_source_task

    task = sync_source_task.delay(source_id)
    return SyncTriggerResponse(task_id=task.id, status="queued")
