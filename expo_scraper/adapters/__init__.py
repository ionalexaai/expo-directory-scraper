"""Adapter registry. One adapter per directory platform, selected by `adapter:` in the config."""

from __future__ import annotations

from expo_scraper.adapters.base import DirectoryAdapter
from expo_scraper.adapters.rx_platform import RXPlatformAdapter

ADAPTERS: dict[str, type[DirectoryAdapter]] = {
    RXPlatformAdapter.name: RXPlatformAdapter,
}


def get_adapter(name: str) -> type[DirectoryAdapter]:
    try:
        return ADAPTERS[name]
    except KeyError:
        known = ", ".join(sorted(ADAPTERS)) or "(none)"
        raise KeyError(f"unknown adapter '{name}'. Known adapters: {known}") from None
