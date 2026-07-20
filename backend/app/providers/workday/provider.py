import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.normalization.text import clean_department, detect_remote_type, location_pins_a_city
from app.providers.base import JobProvider, NormalizedJob
from app.providers.workday.client import WorkdayClient

# Any *.myworkdayjobs.com host — including multi-label prefixes like nvidia.wd5.myworkdayjobs.com.
WORKDAY_HOST_RE = re.compile(r"^[a-z0-9\-\.]+\.myworkdayjobs\.com$", re.IGNORECASE)

# Match strings like "Posted Today", "Posted Yesterday", "Posted 3 Days Ago",
# "Posted 30+ Days Ago". Case-insensitive.
_POSTED_RE = re.compile(
    r"posted\s+(?:(today)|(yesterday)|(\d+)\s*\+?\s*days?)\s*(?:ago)?",
    re.IGNORECASE,
)


def _parse_posted_on(text: str | None) -> datetime | None:
    """Turn Workday's human-readable ``postedOn`` into a UTC datetime estimate.

    Anything we can't parse returns None; caller treats null posted_at as unknown-age
    (kept by the query-time filter since we can't judge).
    """
    if not text:
        return None
    m = _POSTED_RE.search(text)
    if not m:
        return None
    now = datetime.now(timezone.utc)
    if m.group(1):  # today
        return now
    if m.group(2):  # yesterday
        return now - timedelta(days=1)
    if m.group(3):  # N days
        return now - timedelta(days=int(m.group(3)))
    return None


class WorkdayProvider(JobProvider):
    """Workday CXS API. Each Workday customer has a different (host, tenant, site) —
    e.g. ``nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite``. We encode all three
    into a single source_identifier because the JobSource row has one string slot.

    Two big caveats vs the other providers:
      1. ``postedOn`` is a human string like "Posted 3 Days Ago" — we parse it into
         a datetime estimate; anything unparseable stays None.
      2. Description isn't in the list response, only per-posting fetches.
    """

    name = "workday"

    def __init__(self, client: WorkdayClient | None = None):
        self._client = client or WorkdayClient()

    def detect(self, url: str) -> bool:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return bool(WORKDAY_HOST_RE.match(parsed.hostname or ""))

    def extract_source_identifier(self, url: str) -> str | None:
        """Parse a Workday public URL into ``tenant||host||site``.

        Public URLs look like:
          - ``https://<tenant>.<wdN>.myworkdayjobs.com/<site>``
          - ``https://<tenant>.<wdN>.myworkdayjobs.com/en-US/<site>``
          - ``https://<tenant>.<wdN>.myworkdayjobs.com/<site>/job/<location>/<title>_<id>``
        Some tenants embed the tenant differently — best-effort parsing here.
        """
        if not self.detect(url):
            return None
        parsed = urlparse(url if "://" in url else f"https://{url}")
        host = (parsed.hostname or "").lower()
        # Tenant is the first host label.
        tenant = host.split(".")[0]
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            return None
        # Skip a leading locale like "en-US".
        if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", segments[0]) or re.fullmatch(r"[a-z]{2}", segments[0]):
            segments = segments[1:]
        if not segments:
            return None
        # Site is the first remaining segment; ignore anything after (job path, etc.).
        site = segments[0]
        return WorkdayClient.encode_identifier(host, tenant, site)

    def discover(self, company_url: str) -> list[str]:
        raise NotImplementedError(
            "Workday discovery from a company's own site is not implemented; "
            "use the full myworkdayjobs.com URL instead."
        )

    def fetch_jobs(self, source_identifier: str) -> list[dict[str, Any]]:
        return self._client.list_jobs(source_identifier)

    def fetch_job(self, job_url: str) -> dict[str, Any]:  # pragma: no cover - not used by sync
        raise NotImplementedError(
            "Workday per-job fetch requires a separate endpoint per tenant — not wired up."
        )

    def normalize(self, raw_job: dict[str, Any], company_name: str) -> NormalizedJob:
        title = raw_job.get("title") or ""
        location = raw_job.get("locationsText") or None
        external_path = raw_job.get("externalPath") or ""
        # externalPath is guaranteed unique per posting per tenant; use it as source_job_id.
        # We previously used bulletFields[0], but that array contains different content per
        # tenant — sometimes the actual job req ID, sometimes a country name — which caused
        # unique-constraint collisions.
        job_id = external_path or raw_job.get("id") or ""

        # Workday doesn't expose a remote flag; look at the human-readable text only.
        remote_type = detect_remote_type(location, "")
        if remote_type == "remote" and location and location_pins_a_city(location):
            remote_type = "hybrid"

        return NormalizedJob(
            source_provider=self.name,
            source_job_id=job_id,
            company_name=company_name,
            title=title,
            description="",
            canonical_url=external_path,  # relative — display layer can prepend host if it wants
            location=location,
            remote_type=remote_type,
            employment_type=None,
            department=clean_department(None),
            posted_at=_parse_posted_on(raw_job.get("postedOn")),
        )
