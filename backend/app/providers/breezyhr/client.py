import time
from typing import Any

import httpx

RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class BreezyHRAPIError(Exception):
    pass


class BreezyHRClient:
    """Wrapper over BreezyHR's public postings endpoint.

    Endpoint: ``https://<companyId>.breezy.hr/json``. Returns a JSON array of open
    positions. Unauthenticated, no pagination — the endpoint hands back every
    published position at once. Covers many small US startups (a couple to a few
    dozen roles each).
    """

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 10.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _get(self, url: str) -> Any:
        last_error: str | None = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = self._client.get(url, headers={"User-Agent": "job-intel/0.1"})
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            response.raise_for_status()
            return response.json()
        raise BreezyHRAPIError(f"BreezyHR request to {url} failed after retries: {last_error}")

    def list_jobs(self, company_id: str) -> list[dict[str, Any]]:
        url = f"https://{company_id}.breezy.hr/json"
        data = self._get(url)
        return data if isinstance(data, list) else []
