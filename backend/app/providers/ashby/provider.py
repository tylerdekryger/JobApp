from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type
from app.providers.ashby.client import AshbyClient
from app.providers.base import JobProvider, NormalizedJob

ASHBY_HOSTS = {"jobs.ashbyhq.com", "api.ashbyhq.com"}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        # Ashby uses ISO 8601 with a millisecond fraction and "+00:00" tz — fromisoformat
        # handles both in Python 3.11+.
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class AshbyProvider(JobProvider):
    """Ashby is the ATS of choice for modern AI/startup companies (Linear, Cursor, Notion,
    Perplexity, etc.). Its public posting API is much richer than Greenhouse's — it exposes
    ``isRemote`` explicitly and ships both HTML and plain-text descriptions.
    """

    name = "ashby"

    def __init__(self, client: AshbyClient | None = None):
        self._client = client or AshbyClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() in ASHBY_HOSTS

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        segments = [segment for segment in parsed.path.split("/") if segment]
        # Public URLs: https://jobs.ashbyhq.com/<orgId>/<jobId>
        # API URLs:    https://api.ashbyhq.com/posting-api/job-board/<orgId>
        if parsed.hostname == "api.ashbyhq.com":
            # /posting-api/job-board/<orgId>
            if len(segments) >= 3 and segments[0] == "posting-api" and segments[1] == "job-board":
                return segments[2]
            return None
        # jobs.ashbyhq.com — first path segment is the orgId.
        return segments[0] if segments else None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "Ashby board discovery from a company's own site is not implemented; "
            "use a directly submitted board URL (jobs.ashbyhq.com/<orgId>) instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        # Ashby doesn't expose a single-job endpoint publicly; the org's list is the source of
        # truth, so we filter it here. Cheap since boards are small.
        parsed = urlparse(job_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if len(segments) < 2:
            raise ValueError(f"Ashby job URL missing org/id: {job_url}")
        org_id, job_id = segments[0], segments[-1]
        for job in self._client.list_jobs(org_id):
            if str(job.get("id")) == job_id:
                return job
        raise LookupError(f"Ashby job {job_id} not found under org {org_id}")

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        location = raw_job.get("location") or None
        description_html = raw_job.get("descriptionHtml") or ""

        # Ashby's own isRemote flag is authoritative when present. Fall back to the text-based
        # heuristic for hybrid/onsite/unknown so the whole app stays consistent with Greenhouse
        # jobs (remote/hybrid/onsite/unknown, four-valued).
        is_remote = raw_job.get("isRemote")
        if is_remote is True:
            remote_type = "remote"
        elif is_remote is False:
            # Explicitly-not-remote — but let heuristic distinguish hybrid vs onsite.
            heuristic = detect_remote_type(location, description_html)
            remote_type = heuristic if heuristic in {"hybrid", "onsite"} else "onsite"
        else:
            remote_type = detect_remote_type(location, description_html)

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job["id"]),
            company_name=company_name,
            title=raw_job["title"],
            description=description_html,
            canonical_url=raw_job.get("jobUrl") or raw_job.get("applyUrl") or "",
            location=location,
            remote_type=remote_type,
            employment_type=raw_job.get("employmentType"),
            department=clean_department(raw_job.get("department")),
            posted_at=_parse_datetime(raw_job.get("publishedAt") or raw_job.get("updatedAt")),
        )
