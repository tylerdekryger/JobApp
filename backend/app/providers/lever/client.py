import time
from typing import Any

import httpx

# Same retry ladder as the other providers (spec §34).
RETRY_DELAYS = [0, 2, 8, 30]
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LeverAPIError(Exception):
    pass


class LeverClient:
    """Wrapper over Lever's public postings endpoint.

    Lever exposes an unauthenticated JSON list per company at
    ``https://api.lever.co/v0/postings/<slug>?mode=json``. Each element is one job
    posting; the response body is a plain array (unlike Greenhouse/Ashby which wrap
    jobs in an object).
    """

    BASE_URL = "https://api.lever.co/v0/postings"

    def __init__(self, http_client: httpx.Client | None = None, timeout: float = 10.0):
        self._client = http_client or httpx.Client(timeout=timeout)

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
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
        raise LeverAPIError(f"Lever request to {path} failed after retries: {last_error}")

    def list_jobs(self, slug: str) -> list[dict[str, Any]]:
        data = self._get(f"/{slug}", params={"mode": "json"})
        return data if isinstance(data, list) else []
