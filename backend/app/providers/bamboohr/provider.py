from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.bamboohr.client import BambooHRClient

BAMBOO_SUFFIX = ".bamboohr.com"


class BambooHRProvider(JobProvider):
    """BambooHR public careers list. Small-to-mid startups; typically a handful of open
    roles per company. NOTE: BambooHR's list endpoint doesn't expose a ``posted_at`` —
    we leave it null and let ``first_seen_at`` drive the age filter (jobs surface once
    we've seen them for the first time; they age out 30 days later).
    """

    name = "bamboohr"

    def __init__(self, client: BambooHRClient | None = None):
        self._client = client or BambooHRClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower().endswith(BAMBOO_SUFFIX)

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        label = host[: -len(BAMBOO_SUFFIX)]
        return label or None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "BambooHR discovery from a company's own site is not implemented; "
            "use a direct <company>.bamboohr.com URL instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        parsed = urlparse(job_url)
        host = (parsed.hostname or "").lower()
        company_id = host[: -len(BAMBOO_SUFFIX)]
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            raise ValueError(f"BambooHR job URL missing id: {job_url}")
        job_id = segments[-1]
        for job in self._client.list_jobs(company_id):
            if str(job.get("id")) == job_id:
                return job
        raise LookupError(f"BambooHR job {job_id} not found under {company_id}")

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        loc = raw_job.get("location") or {}
        parts = [x for x in (loc.get("city"), loc.get("state")) if x]
        location = ", ".join(parts) or None

        # BambooHR's isRemote is boolean-ish; None = unknown.
        is_remote = raw_job.get("isRemote")
        if is_remote is True:
            remote_type = "hybrid" if location_pins_a_city(location) else "remote"
        elif is_remote is False:
            heuristic = detect_remote_type(location, "")
            remote_type = heuristic if heuristic in {"hybrid", "onsite"} else "onsite"
        else:
            remote_type = detect_remote_type(location, "")

        # Build the public URL to the specific posting.
        canonical_url = ""
        # The API doesn't include the company subdomain — we can't rebuild the URL without
        # the caller's slug. Callers pass source_identifier through fetch_jobs; the sync
        # service records source_url on JobSource. We derive canonical below at display time.
        if raw_job.get("jobOpeningShareLink"):
            canonical_url = raw_job["jobOpeningShareLink"]

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job.get("id") or ""),
            company_name=company_name,
            title=raw_job.get("jobOpeningName") or "",
            description="",
            canonical_url=canonical_url,
            location=location,
            remote_type=remote_type,
            employment_type=raw_job.get("employmentStatusLabel"),
            department=clean_department(raw_job.get("departmentLabel")),
            posted_at=None,  # BambooHR doesn't expose this in the list endpoint.
        )
