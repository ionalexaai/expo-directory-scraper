from pathlib import Path

import pytest

from expo_scraper.config import ConfigError, ScrapeConfig
from expo_scraper.exporters import write_csv
from expo_scraper.models import CSV_HEADERS, Exhibitor


def test_from_yaml_splits_core_and_adapter_options(tmp_path: Path):
    cfg_file = tmp_path / "config" / "job.yaml"
    cfg_file.parent.mkdir()
    cfg_file.write_text(
        "name: demo\nadapter: rx_platform\ndirectory_url: https://x\noutput_csv: output/demo.csv\n"
        "locale: EN-US\nrx:\n  event_id: evt-1\n",
        encoding="utf-8",
    )
    cfg = ScrapeConfig.from_yaml(cfg_file)
    assert cfg.name == "demo"
    assert cfg.locale == "en-us"
    assert cfg.adapter_options == {"rx": {"event_id": "evt-1"}}
    # output is resolved relative to the project root (parent of config/)
    assert cfg.resolve_output() == (tmp_path / "output" / "demo.csv").resolve()
    assert cfg.resolve_output("C:/abs/out.csv") == Path("C:/abs/out.csv")


def test_from_yaml_requires_core_keys(tmp_path: Path):
    cfg_file = tmp_path / "bad.yaml"
    cfg_file.write_text("name: demo\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        ScrapeConfig.from_yaml(cfg_file)


def test_write_csv_uses_friendly_headers_and_bom(tmp_path: Path):
    out = write_csv([Exhibitor(company_name="A, Inc.", description="line1\nline2")], tmp_path / "o.csv")
    raw = out.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert text.splitlines()[0] == ",".join(CSV_HEADERS.values())
    assert '"A, Inc."' in text
