import time
from typing import Any

import httpx

RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
PAGE_LIMIT = 20  # Workday's per-request cap
MAX_PAGES = 10


class WorkdayAPIError(Exception):
    pass


class WorkdayClient:
    """Wrapper over Workday's per-tenant CXS jobs endpoint.

    Endpoint shape (POST): ``https://<host>/wday/cxs/<tenant>/<site>/jobs``
    Body: ``{"limit": N, "offset": M, "searchText": "", "appliedFacets": {}}``.
    Unauthenticated for public postings. Each Workday customer has a different
    ``(host, tenant, site)`` — we can't guess it; the caller passes them explicitly.

    We encode all three into a single ``source_identifier`` slot using a delimiter,
    since the JobSource schema only has one string column for the token.
    """

    DELIM = "||"  # unlikely to collide with anything in real tenant/site names

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 15.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _post(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        last_error: str | None = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = self._client.post(
                    url,
                    json=body,
                    headers={"User-Agent": "job-intel/0.1", "Accept": "application/json"},
                )
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            response.raise_for_status()
            return response.json()
        raise WorkdayAPIError(f"Workday request to {url} failed after retries: {last_error}")

    @classmethod
    def encode_identifier(cls, host: str, tenant: str, site: str) -> str:
        return f"{tenant}{cls.DELIM}{host}{cls.DELIM}{site}"

    @classmethod
    def decode_identifier(cls, identifier: str) -> tuple[str, str, str]:
        parts = identifier.split(cls.DELIM)
        if len(parts) != 3:
            raise ValueError(f"Bad Workday identifier {identifier!r}; expected tenant||host||site")
        tenant, host, site = parts
        return tenant, host, site

    def list_jobs(self, identifier: str) -> list[dict[str, Any]]:
        tenant, host, site = self.decode_identifier(identifier)
        url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        jobs: list[dict[str, Any]] = []
        offset = 0
        for _ in range(MAX_PAGES):
            data = self._post(url, {
                "limit": PAGE_LIMIT,
                "offset": offset,
                "searchText": "",
                "appliedFacets": {},
            })
            postings = data.get("jobPostings") or []
            jobs.extend(postings)
            total = int(data.get("total") or 0)
            if not postings or len(jobs) >= total:
                break
            offset += PAGE_LIMIT
        return jobs
