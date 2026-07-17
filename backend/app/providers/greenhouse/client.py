import time
from typing import Any

import httpx

# spec §34: attempt 1 immediate, then 2s, 8s, 30s
RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class GreenhouseAPIError(Exception):
    pass


class GreenhouseClient:
    BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

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
        raise GreenhouseAPIError(f"Greenhouse request to {path} failed after retries: {last_error}")

    def list_jobs(self, board_token: str) -> list[dict[str, Any]]:
        data = self._get(f"/{board_token}/jobs", params={"content": "true"})
        return data.get("jobs", [])

    def get_job(self, board_token: str, job_id: str) -> dict[str, Any]:
        return self._get(f"/{board_token}/jobs/{job_id}", params={"questions": "true"})
