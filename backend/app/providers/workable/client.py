import time
from typing import Any

import httpx

RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class WorkableAPIError(Exception):
    pass


class WorkableClient:
    """Wrapper over Workable's public widget API.

    Endpoint: ``https://apply.workable.com/api/v1/widget/accounts/<token>``.
    Unauthenticated. Returns ``{"name", "description", "jobs": [...]}`` in one call.
    """

    BASE_URL = "https://apply.workable.com/api/v1/widget/accounts"

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 12.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _get(self, path: str) -> dict[str, Any]:
        last_error: str | None = None
        for delay in RETRY_DELAYS:
            if delay:
                time.sleep(delay)
            try:
                response = self._client.get(f"{self.BASE_URL}{path}", headers={"User-Agent": "job-intel/0.1"})
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {exc}"
                continue
            if response.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                continue
            response.raise_for_status()
            return response.json()
        raise WorkableAPIError(f"Workable request to {path} failed after retries: {last_error}")

    def list_jobs(self, token: str) -> list[dict[str, Any]]:
        data = self._get(f"/{token}")
        return data.get("jobs", []) if isinstance(data, dict) else []

    def get_meta(self, token: str) -> dict[str, Any]:
        """Return the top-level account info ({name, description, jobs})."""
        return self._get(f"/{token}")
