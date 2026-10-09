"""Orchestrates one scrape: discover -> list -> enrich (threaded) -> write CSV."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from expo_scraper.adapters import get_adapter
from expo_scraper.config import ScrapeConfig
from expo_scraper.exporters import write_csv
from expo_scraper.http import RateLimiter, build_session
from expo_scraper.models import Exhibitor

log = logging.getLogger(__name__)


@dataclass
class RunSummary:
    config_name: str
    output_path: Path
    listed: int
    exported: int
    with_linkedin: int
    with_categories: int
    with_email: int
    with_website: int
    seconds: float

    def pretty(self) -> str:
        return (
            f"{self.config_name}: exported {self.exported}/{self.listed} exhibitors to {self.output_path}\n"
            f"  website: {self.with_website}  email: {self.with_email}  "
            f"linkedin: {self.with_linkedin}  categories: {self.with_categories}\n"
            f"  took {self.seconds:.0f}s"
        )


def run(config: ScrapeConfig, output_override: str | None = None, limit: int | None = None,
        concurrency: int | None = None) -> RunSummary:
    started = time.monotonic()
    session = build_session(config.user_agent)
    limiter = RateLimiter(config.request_delay_seconds)
    adapter = get_adapter(config.adapter)(config, session, limiter)

    adapter.discover()
    records: list[dict[str, Any]] = adapter.list_exhibitors()
    log.info("Listed %d exhibitors", len(records))
    if limit is not None:
        records = records[:limit]
        log.info("Limiting run to first %d exhibitors", len(records))

    workers = concurrency or config.concurrency
    exhibitors: list[Exhibitor] = []
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # map() preserves listing order, so the CSV matches the directory ordering.
        for exhibitor in pool.map(adapter.build_exhibitor, records):
            exhibitors.append(exhibitor)
            done += 1
            if done % 25 == 0 or done == len(records):
                log.info("Enriched %d/%d", done, len(records))

    output_path = config.resolve_output(output_override)
    write_csv(exhibitors, output_path)

    return RunSummary(
        config_name=config.name,
        output_path=output_path,
        listed=len(records),
        exported=len(exhibitors),
        with_linkedin=sum(1 for e in exhibitors if e.linkedin_url),
        with_categories=sum(1 for e in exhibitors if e.product_categories),
        with_email=sum(1 for e in exhibitors if e.email),
        with_website=sum(1 for e in exhibitors if e.website),
        seconds=time.monotonic() - started,
    )
