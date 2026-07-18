import time
from typing import Any

import httpx

# Mirrors the Greenhouse client's retry ladder (spec §34).
RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class AshbyAPIError(Exception):
    pass


class AshbyClient:
    """Thin wrapper over Ashby's public posting API.

    Ashby exposes an unauthenticated JSON endpoint per company:
        https://api.ashbyhq.com/posting-api/job-board/<orgId>?includeCompensation=true
    which returns ``{"jobs": [...], "apiVersion": ...}``.
    """

    BASE_URL = "https://api.ashbyhq.com/posting-api/job-board"

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 10.0):
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
        raise AshbyAPIError(f"Ashby request to {path} failed after retries: {last_error}")

    def list_jobs(self, org_id: str) -> list[dict[str, Any]]:
        data = self._get(f"/{org_id}", params={"includeCompensation": "true"})
        # Ashby only returns publicly-listed roles by default; filter to isListed anyway
        # in case the API ever changes to include drafts.
        return [j for j in data.get("jobs", []) if j.get("isListed", True)]
