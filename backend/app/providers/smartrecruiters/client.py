import time
from typing import Any

import httpx

RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
PAGE_LIMIT = 100  # max SmartRecruiters allows per page


class SmartRecruitersAPIError(Exception):
    pass


class SmartRecruitersClient:
    """Wrapper over SmartRecruiters' public postings endpoint.

    Endpoint: ``https://api.smartrecruiters.com/v1/companies/<identifier>/postings``.
    Unauthenticated. Paginated (default limit 10, max 100). We loop until we've
    collected everything or hit a reasonable cap.
    """

    BASE_URL = "https://api.smartrecruiters.com/v1/companies"

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 15.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        last_error: str | None = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = self._client.get(f"{self.BASE_URL}{path}", params=params)
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            response.raise_for_status()
            return response.json()
        raise SmartRecruitersAPIError(
            f"SmartRecruiters request to {path} failed after retries: {last_error}"
        )

    def list_jobs(self, company_id: str, *, max_pages: int = 10) -> list[dict[str, Any]]:
        jobs: list[dict[str, Any]] = []
        offset = 0
        for _ in range(max_pages):
            page = self._get(
                f"/{company_id}/postings",
                params={"limit": str(PAGE_LIMIT), "offset": str(offset)},
            )
            content = page.get("content") or []
            jobs.extend(content)
            total = int(page.get("totalFound") or 0)
            if not content or len(jobs) >= total:
                break
            offset += PAGE_LIMIT
        return jobs

    def get_job(self, posting_id: str) -> dict[str, Any]:
        # SmartRecruiters exposes per-posting details at v1/postings/<id>
        return self._get(f"/../postings/{posting_id}")
