import time
from typing import Any

import httpx

RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class BambooHRAPIError(Exception):
    pass


class BambooHRClient:
    """BambooHR public jobs list. Endpoint: ``https://<company>.bamboohr.com/careers/list``.
    Returns ``{"result": [...]}``. Unauthenticated. No pagination.
    """

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 10.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _get(self, url: str) -> dict[str, Any]:
        last_error: str | None = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = self._client.get(
                    url,
                    headers={"User-Agent": "job-intel/0.1", "Accept": "application/json"},
                    follow_redirects=True,
                )
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            response.raise_for_status()
            return response.json()
        raise BambooHRAPIError(f"BambooHR request to {url} failed after retries: {last_error}")

    def list_jobs(self, company_id: str) -> list[dict[str, Any]]:
        data = self._get(f"https://{company_id}.bamboohr.com/careers/list")
        return data.get("result", []) if isinstance(data, dict) else []
