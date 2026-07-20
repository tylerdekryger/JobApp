from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.smartrecruiters.client import SmartRecruitersClient

SR_HOSTS = {"jobs.smartrecruiters.com", "careers.smartrecruiters.com", "api.smartrecruiters.com"}


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


class SmartRecruitersProvider(JobProvider):
    """SmartRecruiters public postings API. Covers many mid-market and large US
    employers (Visa, NBCUniversal, ServiceTitan, Xplor, etc.). The list endpoint
    returns structured location + remote/hybrid booleans but no description body —
    that's fine for the app's title-based filtering and per-row fit/market checks."""

    name = "smartrecruiters"

    def __init__(self, client: SmartRecruitersClient | None = None):
        self._client = client or SmartRecruitersClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return (parsed.hostname or "").lower() in SR_HOSTS

    def extract_source_identifier(self, url: str) -> str | None:
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        segments = [s for s in parsed.path.split("/") if s]
        if parsed.hostname == "api.smartrecruiters.com":
            # /v1/companies/<id>/postings
            if len(segments) >= 3 and segments[0] == "v1" and segments[1] == "companies":
                return segments[2]
            return None
        # jobs.smartrecruiters.com/<companyId>[/<postingId>-slug]
        return segments[0] if segments else None

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "SmartRecruiters discovery from a company's own site is not implemented; "
            "use a direct jobs.smartrecruiters.com/<companyId> URL instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:
        parsed = urlparse(job_url)
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            raise ValueError(f"SmartRecruiters job URL missing path: {job_url}")
        # /<companyId>/<postingId>-slug — the postingId is before the first dash.
        posting_ref = segments[-1]
        posting_id = posting_ref.split("-", 1)[0]
        return self._client.get_job(posting_id)

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        loc = raw_job.get("location") or {}
        location = loc.get("fullLocation") or " ".join(
            filter(None, [loc.get("city"), loc.get("region"), loc.get("country", "").upper()])
        ) or None

        # SmartRecruiters exposes explicit remote/hybrid flags — same policy as Ashby/Lever.
        is_remote = bool(loc.get("remote"))
        is_hybrid = bool(loc.get("hybrid"))
        if is_remote:
            remote_type = "hybrid" if location_pins_a_city(location) else "remote"
        elif is_hybrid:
            remote_type = "hybrid"
        else:
            remote_type = detect_remote_type(location, "")

        department = (raw_job.get("department") or {}).get("label")
        function = (raw_job.get("function") or {}).get("label")
        employment = (raw_job.get("typeOfEmployment") or {}).get("label")

        # Canonical URL — SmartRecruiters posts live at jobs.smartrecruiters.com/<companyId>/<postingId>-slug
        company_id = (raw_job.get("company") or {}).get("identifier") or ""
        canonical_url = (
            f"https://jobs.smartrecruiters.com/{company_id}/{raw_job.get('id', '')}"
            if company_id and raw_job.get("id")
            else ""
        )

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=str(raw_job["id"]),
            company_name=company_name,
            title=raw_job.get("name") or "",
            description="",  # not present in list endpoint; per-job fetch is expensive
            canonical_url=canonical_url,
            location=location,
            remote_type=remote_type,
            employment_type=employment,
            department=clean_department(department or function),
            posted_at=_parse_dt(raw_job.get("releasedDate") or raw_job.get("createdOn")),
        )
