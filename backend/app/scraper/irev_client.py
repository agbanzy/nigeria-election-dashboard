"""Thin HTTP client for the INEC IReV proxy.

Retries on 429/5xx with backoff. Token bucket caps to 30 req/min.
Identity headers mirror the legacy `election_dashboard.py` (line ~95) so the proxy
won't fingerprint us as a new client.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.inecelectionresults.ng",
    "Referer": "https://www.inecelectionresults.ng/",
    "Connection": "keep-alive",
}


class TokenBucket:
    """Simple thread-safe token bucket. Default: 30 tokens / 60s."""

    def __init__(self, capacity: int = 30, refill_seconds: float = 60.0) -> None:
        self.capacity = capacity
        self.tokens = float(capacity)
        self.refill_rate = capacity / refill_seconds
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self, count: int = 1) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self.last = now
                if self.tokens >= count:
                    self.tokens -= count
                    return
                wait = (count - self.tokens) / self.refill_rate
            time.sleep(min(wait, 2.0))


class IrevClient:
    def __init__(self, base_url: str, api_key: str, *, requests_per_minute: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.bucket = TokenBucket(capacity=requests_per_minute, refill_seconds=60.0)
        self._session = requests.Session()

        retries = Retry(
            total=4,
            backoff_factor=5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retries, pool_connections=10, pool_maxsize=10, pool_block=False
        )
        self._session.mount("https://", adapter)
        self._session.mount("http://", adapter)
        self._session.headers.update(_DEFAULT_HEADERS)
        if api_key:
            self._session.headers["x-api-key"] = api_key

    def get(self, path: str, *, timeout: int = 90, params: dict[str, Any] | None = None) -> Any:
        self.bucket.acquire()
        url = f"{self.base_url}/{path.lstrip('/')}"
        self._session.headers["x-api-rt"] = str(int(time.time() * 1000))
        log.debug("GET %s params=%s", url, params)
        resp = self._session.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        if not resp.content:
            return None
        return resp.json()

    def list_elections(self, *, election_type_id: str) -> Any:
        return self.get("/elections", params={"election_type": election_type_id})

    def election_stats(self, election_id: str) -> Any:
        return self.get(f"/elections/{election_id}/result/stats")

    def lga_state(self, election_id: str, state_id: int) -> Any:
        return self.get(f"/elections/{election_id}/lga/state/{state_id}")

    def pus_for_ward(self, election_id: str, ward_id: str) -> Any:
        return self.get(f"/elections/{election_id}/pus", params={"ward": ward_id})
