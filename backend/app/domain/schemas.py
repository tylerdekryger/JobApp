from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceCreateRequest(BaseModel):
    url: str
    company_name: str | None = None


class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    provider: str
    source_url: str
    source_identifier: str
    status: str
    last_successful_sync: datetime | None
    last_attempted_sync: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class SyncTriggerResponse(BaseModel):
    task_id: str
    status: str


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    job_source_id: int
    external_job_id: str
    canonical_url: str
    title: str
    description: str
    location: str | None
    remote_type: str | None
    employment_type: str | None
    department: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    last_content_change_at: datetime
    status: str


class JobListResponse(BaseModel):
    items: list[JobResponse]
    limit: int
    offset: int
    total: int
