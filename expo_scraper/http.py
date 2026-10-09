"""HTTP session with retries plus a tiny thread-safe rate limiter."""

from __future__ import annotations

import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_session(user_agent: str, retries: int = 4, backoff: float = 0.6) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "POST"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=16, pool_maxsize=16)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": user_agent, "Accept": "application/json, text/html;q=0.9"})
    return session


class RateLimiter:
    """Enforce a minimum interval between requests across all threads."""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self.min_interval == 0:
            return
        with self._lock:
            now = time.monotonic()
            delay = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self.min_interval
        if delay > 0:
            time.sleep(delay)
