"""Base class every directory adapter implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

import requests

from expo_scraper.config import ScrapeConfig
from expo_scraper.http import RateLimiter
from expo_scraper.models import Exhibitor


class DirectoryAdapter(ABC):
    """Three-step contract: discover site settings, list records, enrich each record."""

    name: ClassVar[str]

    def __init__(self, config: ScrapeConfig, session: requests.Session, limiter: RateLimiter) -> None:
        self.config = config
        self.session = session
        self.limiter = limiter

    @abstractmethod
    def discover(self) -> None:
        """Fetch whatever the directory page exposes (API keys, ids, URL formats)."""

    @abstractmethod
    def list_exhibitors(self) -> list[dict[str, Any]]:
        """Return raw listing records, one per exhibitor, in directory order."""

    @abstractmethod
    def build_exhibitor(self, record: dict[str, Any]) -> Exhibitor:
        """Fetch the detail page data for one listing record and map it to an Exhibitor."""

    def describe(self) -> dict[str, Any]:
        """Settings worth printing/logging after discover(). Secrets should be masked."""
        return {}
