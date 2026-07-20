from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.workable.client import WorkableClient

WORKABLE_HOSTS = {"apply.workable.com", "jobs.workable.com"}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        # published_on / created_at come as "YYYY-MM-DD" (naive) — assume UTC midnight
        # so downstream comparisons against tz-aware "now" don't blow up.
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


class WorkableProvider(JobProvider):
    """Workable's public widget API. Covers many SMB/mid-market SaaS + agencies
    (Writesonic, OneReach, Datawow, etc.). Uses the v1 widget endpoint because the
    v3 API is authenticated. Description isn't in the list response — fine for
    title-based filtering and per-row analysis/market-check flows.
    """

    name = "workable"

    def __init__(self, client: WorkableClient | None = None):
        self._client = client or WorkableClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() in WORKABLE_HOSTS

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        segments = [s for s in parsed.path.split("/") if s]
        # apply.workable.com/<token>[/<jobShortcode>]  — token is the first segment.
        # apply.workable.com/j/<shortcode>             — this is a single-job URL; no account token here.
        if segments and segments[0] == "j":
            return None
        return segments[0] if segments else None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "Workable discovery from a company's own site is not implemented; "
            "use a direct apply.workable.com/<token> URL instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        # Per-job data isn't in the widget list endpoint; look it up by shortcode.
        parsed = urlparse(job_url)
        segments = [s for s in parsed.path.split("/") if s]
        shortcode = segments[-1] if segments else ""
        for job in self._client.list_jobs(segments[0]) if len(segments) > 1 else []:
            if job.get("shortcode") == shortcode:
                return job
        raise LookupError(f"Workable job {shortcode} not found in {job_url}")

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        # Prefer the joined locations list if present, else stitch city/state/country.
        locs = raw_job.get("locations") or []
        parts: list[str] = []
        for loc in locs:
            city = (loc.get("city") or "").strip()
            region = (loc.get("region") or "").strip()
            country = (loc.get("country") or "").strip()
            piece = ", ".join(x for x in (city, region, country) if x)
            if piece:
                parts.append(piece)
        if not parts:
            piece = ", ".join(
                x for x in (raw_job.get("city"), raw_job.get("state"), raw_job.get("country")) if x
            )
            if piece:
                parts.append(piece)
        location = "; ".join(parts) or None

        # telecommuting=true is Workable's "remote-friendly" flag; same downgrade policy
        # as Ashby/Lever/BreezyHR when the location string pins a specific city.
        if raw_job.get("telecommuting"):
            remote_type = "hybrid" if location_pins_a_city(location) else "remote"
        else:
            remote_type = detect_remote_type(location, "")

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job.get("shortcode") or raw_job.get("code") or ""),
            company_name=company_name,
            title=raw_job.get("title") or "",
            description="",
            canonical_url=raw_job.get("url") or raw_job.get("shortlink") or "",
            location=location,
            remote_type=remote_type,
            employment_type=raw_job.get("employment_type"),
            department=clean_department(raw_job.get("department") or raw_job.get("function")),
            posted_at=_parse_dt(raw_job.get("published_on") or raw_job.get("created_at")),
        )
