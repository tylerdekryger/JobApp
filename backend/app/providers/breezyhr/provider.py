from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.breezyhr.client import BreezyHRClient

BREEZY_HOST_SUFFIX = ".breezy.hr"


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class BreezyHRProvider(JobProvider):
    """BreezyHR public postings API. Best for smaller startups (typically 1-15 open
    roles). Each company's board is at ``<companyId>.breezy.hr/json``.
    """

    name = "breezyhr"

    def __init__(self, client: BreezyHRClient | None = None):
        self._client = client or BreezyHRClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        return host.endswith(BREEZY_HOST_SUFFIX)

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        # https://<companyId>.breezy.hr[/…]  → companyId is the leading label.
        label = host[: -len(BREEZY_HOST_SUFFIX)]
        return label or None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "BreezyHR discovery from a company's own site is not implemented; "
            "use a direct <company>.breezy.hr URL instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        parsed = urlparse(job_url)
        host = (parsed.hostname or "").lower()
        company_id = host[: -len(BREEZY_HOST_SUFFIX)]
        segments = [s for s in parsed.path.split("/") if s]
        # URL pattern: /p/<friendlyId>-slug
        if len(segments) < 2 or segments[0] != "p":
            raise ValueError(f"BreezyHR job URL missing /p/<id>: {job_url}")
        friendly_id = segments[1].split("-", 1)[0]
        for job in self._client.list_jobs(company_id):
            if job.get("friendly_id") == friendly_id or job.get("id") == friendly_id:
                return job
        raise LookupError(f"BreezyHR job {friendly_id} not found under {company_id}")

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        loc = raw_job.get("location") or {}
        country = (loc.get("country") or {}).get("name") or ""
        location_name = loc.get("name") or country or None
        is_remote_flag = bool(loc.get("is_remote"))

        # Same policy as Ashby/Lever: trust the ATS remote flag unless the location
        # names a specific city (then treat as hybrid so it drops from the default view).
        if is_remote_flag:
            remote_type = "hybrid" if location_pins_a_city(location_name) else "remote"
        else:
            remote_type = detect_remote_type(location_name, "")

        employment = (raw_job.get("type") or {}).get("name")

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job.get("id") or raw_job.get("friendly_id") or ""),
            company_name=company_name,
            title=raw_job.get("name") or "",
            description="",  # not in list endpoint
            canonical_url=raw_job.get("url") or "",
            location=location_name,
            remote_type=remote_type,
            employment_type=employment,
            department=clean_department(raw_job.get("department")),
            posted_at=_parse_dt(raw_job.get("published_date") or raw_job.get("updated_date")),
        )
