from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.models import Company, Job
from app.domain.schemas import CompanyListResponse, CompanySummary

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=CompanyListResponse)
def list_companies(db: Session = Depends(get_db)) -> CompanyListResponse:
    active_job_count = func.count(Job.id).filter(Job.status == "active")
    rows = db.execute(
        select(Company.id, Company.name, active_job_count.label("active_job_count"))
        .outerjoin(Job, Job.company_id == Company.id)
        .group_by(Company.id, Company.name)
        .order_by(Company.name)
    ).all()

    items = [CompanySummary(id=row.id, name=row.name, active_job_count=row.active_job_count) for row in rows]
    return CompanyListResponse(items=items, total=len(items))
