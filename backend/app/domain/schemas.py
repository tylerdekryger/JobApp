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


class SyncResultResponse(BaseModel):
    source_id: int
    jobs_found: int
    jobs_added: int
    jobs_updated: int
    jobs_removed: int
    duration_seconds: float


class SourceSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    company_name: str
    provider: str
    source_url: str
    source_identifier: str
    status: str
    last_successful_sync: datetime | None
    last_attempted_sync: datetime | None
    last_error: str | None
    active_job_count: int


class SourceListResponse(BaseModel):
    items: list[SourceSummary]
    total: int


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    company_name: str | None = None
    job_source_id: int
    external_job_id: str
    canonical_url: str
    title: str
    description: str
    description_clean: str  # raw description with per-source boilerplate stripped
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


class CompanySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    active_job_count: int


class CompanyListResponse(BaseModel):
    items: list[CompanySummary]
    total: int


class FacetValue(BaseModel):
    value: str
    count: int


class FacetsResponse(BaseModel):
    departments: list[FacetValue]
    locations: list[FacetValue]
    companies: list[FacetValue]
