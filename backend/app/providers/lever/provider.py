from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.lever.client import LeverClient

LEVER_HOSTS = {"jobs.lever.co", "api.lever.co"}


def _parse_lever_datetime(value: Any) -> datetime | None:
    """Lever returns createdAt as milliseconds since epoch (int)."""
    if value is None:
        return None
    try:
        ms = int(value)
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


class LeverProvider(JobProvider):
    """Lever's public postings API. Powers many mid-market SaaS + Series A/B startups
    (Palantir, Shield AI, Ro, Greenlight, Sword Health, etc.). Schema is close enough
    to Ashby's — workplaceType is authoritative for remote/hybrid/onsite, country
    gives a strong US-eligibility signal, and categories.allLocations is a list."""

    name = "lever"

    def __init__(self, client: LeverClient | None = None):
        self._client = client or LeverClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() in LEVER_HOSTS

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        segments = [s for s in parsed.path.split("/") if s]
        # Public URLs: https://jobs.lever.co/<slug>[/<jobId>]
        # API URLs:    https://api.lever.co/v0/postings/<slug>
        if parsed.hostname == "api.lever.co":
            if len(segments) >= 3 and segments[0] == "v0" and segments[1] == "postings":
                return segments[2]
            return None
        return segments[0] if segments else None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "Lever board discovery from a company's own site is not implemented; "
            "use a directly submitted board URL (jobs.lever.co/<slug>) instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        # Lever's public listing is the source of truth; filter locally.
        parsed = urlparse(job_url)
        segments = [s for s in parsed.path.split("/") if s]
        if len(segments) < 2:
            raise ValueError(f"Lever job URL missing slug/id: {job_url}")
        slug, job_id = segments[0], segments[-1]
        for job in self._client.list_jobs(slug):
            if str(job.get("id")) == job_id:
                return job
        raise LookupError(f"Lever job {job_id} not found under slug {slug}")

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        categories = raw_job.get("categories") or {}
        # Prefer allLocations joined (some rows list several cities); fall back to location.
        all_locs = categories.get("allLocations") or []
        location = "; ".join(all_locs) if all_locs else (categories.get("location") or None)
        description_html = raw_job.get("description") or raw_job.get("descriptionBody") or ""
        wp = (raw_job.get("workplaceType") or "").lower()

        # Same policy as Ashby: trust the ATS's workplace flag for "remote", but if the
        # location pins a specific city, downgrade to "hybrid" (default view drops it).
        if wp == "remote":
            remote_type = "hybrid" if location_pins_a_city(location) else "remote"
        elif wp == "hybrid":
            remote_type = "hybrid"
        elif wp == "on-site" or wp == "onsite":
            remote_type = "onsite"
        elif wp == "unspecified" or not wp:
            remote_type = detect_remote_type(location, description_html)
        else:
            remote_type = detect_remote_type(location, description_html)

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job["id"]),
            company_name=company_name,
            title=raw_job.get("text") or "",
            description=description_html,
            canonical_url=raw_job.get("hostedUrl") or raw_job.get("applyUrl") or "",
            location=location,
            remote_type=remote_type,
            employment_type=categories.get("commitment"),
            department=clean_department(categories.get("team")),
            posted_at=_parse_lever_datetime(raw_job.get("createdAt")),
        )
