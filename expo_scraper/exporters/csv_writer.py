"""Write Exhibitor rows to a CSV that opens cleanly in Excel and Google Sheets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from expo_scraper.models import CSV_HEADERS, FIELD_NAMES, Exhibitor


def write_csv(rows: Iterable[Exhibitor], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: the BOM makes Excel detect UTF-8; Google Sheets ignores it.
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELD_NAMES, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(CSV_HEADERS)
        for row in rows:
            writer.writerow(row.as_row())
    return path
