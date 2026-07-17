from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class NormalizedJob:
    source_provider: str
    source_job_id: str
    company_name: str
    title: str
    description: str
    canonical_url: str
    location: str | None = None
    remote_type: str | None = None
    employment_type: str | None = None
    department: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    posted_at: datetime | None = None


class JobProvider(ABC):
    """Shared interface every ATS connector must implement.

    Implementations must never leak provider-specific raw fields past
    `normalize()` — everything downstream of a provider only ever sees
    `NormalizedJob`.
    """

    name: str

    @abstractmethod
    def detect(self, url: str) -> bool:
        """Return True if this provider can handle the given career-page/board URL."""

    @abstractmethod
    def extract_source_identifier(self, url: str) -> str | None:
        """Given a URL this provider detects, extract its source_identifier (e.g. board token)."""

    @abstractmethod
    def discover(self, company_url: str) -> list[str]:
        """Given a company's own website, find URLs of career boards hosted by this provider."""

    @abstractmethod
    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        """Fetch the raw job listing for a given source (e.g. a Greenhouse board token)."""

    @abstractmethod
    def fetch_job(self, job_url: str) -> dict[str, Any]:
        """Fetch a single raw job by its canonical URL."""

    @abstractmethod
    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        """Convert a raw, provider-specific job payload into a NormalizedJob."""
