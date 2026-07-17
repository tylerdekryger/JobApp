from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type
from app.providers.base import JobProvider, NormalizedJob
from app.providers.greenhouse.client import GreenhouseClient

GREENHOUSE_HOSTS = {"boards.greenhouse.io", "job-boards.greenhouse.io"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class GreenhouseProvider(JobProvider):
    name = "greenhouse"

    def __init__(self, client: GreenhouseClient | None = None):
        self._client = client or GreenhouseClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() in GREENHOUSE_HOSTS

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        segments = [segment for segment in parsed.path.split("/") if segment]
        return segments[0] if segments else None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "Greenhouse board discovery from a company's own site is not implemented yet; "
            "use a directly submitted board URL instead (spec §11 Mode D)."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        parsed = urlparse(job_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        # expected shape: /<board_token>/jobs/<job_id>
        board_token, job_id = segments[0], segments[-1]
        return self._client.get_job(board_token, job_id)

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        departments = raw_job.get("departments") or []
        raw_department = departments[0]["name"] if departments else None
        location = (raw_job.get("location") or {}).get("name")
        description = raw_job.get("content") or ""

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job["id"]),
            company_name=company_name,
            title=raw_job["title"],
            description=description,
            canonical_url=raw_job["absolute_url"],
            location=location,
            remote_type=detect_remote_type(location, description),
            department=clean_department(raw_department),
            posted_at=_parse_datetime(raw_job.get("first_published") or raw_job.get("updated_at")),
        )
