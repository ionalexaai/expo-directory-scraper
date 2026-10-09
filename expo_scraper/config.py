"""Load a scrape job definition from a YAML file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass
class ScrapeConfig:
    """One directory to scrape. See config/*.yaml for examples."""

    name: str
    adapter: str
    directory_url: str
    output_csv: str
    locale: str = "en-us"
    request_delay_seconds: float = 0.25
    concurrency: int = 4
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
    )
    adapter_options: dict[str, Any] = field(default_factory=dict)
    config_path: Path | None = None

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ScrapeConfig":
        path = Path(path)
        with path.open("r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: top level must be a mapping")

        required = ("name", "adapter", "directory_url", "output_csv")
        missing = [k for k in required if not raw.get(k)]
        if missing:
            raise ConfigError(f"{path}: missing required keys: {', '.join(missing)}")

        known = {f for f in cls.__dataclass_fields__ if f not in ("adapter_options", "config_path")}
        kwargs = {k: v for k, v in raw.items() if k in known}
        # Everything the core doesn't understand is handed to the adapter.
        adapter_options = {k: v for k, v in raw.items() if k not in known}
        cfg = cls(adapter_options=adapter_options, config_path=path, **kwargs)
        cfg.locale = cfg.locale.lower()
        if cfg.concurrency < 1:
            raise ConfigError("concurrency must be >= 1")
        if cfg.request_delay_seconds < 0:
            raise ConfigError("request_delay_seconds must be >= 0")
        return cfg

    def resolve_output(self, override: str | None = None) -> Path:
        """Output path, relative to the config file's parent directory unless absolute."""
        target = Path(override or self.output_csv)
        if target.is_absolute() or self.config_path is None:
            return target
        return (self.config_path.parent.parent / target).resolve()
