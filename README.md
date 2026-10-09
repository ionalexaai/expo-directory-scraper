# expo-directory-scraper

Pull trade-show exhibitor directories into a clean CSV. One YAML config per
directory, one adapter per directory platform, no browser automation.

Built for the ISC West exhibitor directory first. The adapter targets the RX
(Reed Exhibitions) show platform, so other RX shows (ISC East, and most
`discover*.com` / `*.rxglobal.com` event sites) should work by pointing a new
config at their directory URL.

## Output columns

| Column | Source |
| --- | --- |
| Company Name | listing |
| Website | listing |
| Email | listing |
| Stand # | listing |
| LinkedIn Company URL | detail page social links (picks LinkedIn regardless of icon order) |
| Why visit our stand | detail page |
| Description | detail page |
| Brands we will feature | detail page |
| Product Categories | detail page, the full list behind "Show all categories", comma separated |
| Source URL | the detail page URL the directory links to |

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows   (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt

python -m expo_scraper --config config/isc_west_2025.yaml
```

The CSV lands at `output/isc_west_2025_exhibitors.csv` (UTF-8 with BOM, so it
opens correctly in Excel and imports cleanly into Google Sheets).

Useful flags:

```bash
python -m expo_scraper -c config/isc_west_2025.yaml --limit 20        # smoke test on 20 exhibitors
python -m expo_scraper -c config/isc_west_2025.yaml -o C:\tmp\isc.csv  # custom output path
python -m expo_scraper -c config/a.yaml -c config/b.yaml               # several directories in one go
python -m expo_scraper -c config/isc_west_2025.yaml -v                 # debug logging
```

## How it works

RX directory pages are React apps that render from two public data sources.
Instead of driving a browser through 800+ "click company, click Show all
categories" cycles, the adapter calls those sources directly:

1. **Discover.** Fetch the directory URL once and read the embedded
   `reactSettings` JSON: Algolia app id / search key, event and edition ids, the
   API client id and the detail-page URL format.
2. **List.** Query the Algolia index filtered to the current edition's
   exhibitors. This is the same call the directory page makes and returns name,
   website, email, stand, description and brands for every exhibitor.
3. **Enrich.** For each exhibitor, call the public GraphQL endpoint the detail
   page uses. That returns the social links and the complete category list.
   Requests are rate limited and run on a small thread pool.
4. **Export.** Write one row per exhibitor in directory order.

If a detail call fails, the row is still written from listing data and a warning
is logged, so one flaky page never kills a run.

## Configuration

```yaml
name: isc-west-2025
adapter: rx_platform
directory_url: "https://www.discoverisc.com/west/en-us/2025-exhibitors/exhibitor-directory.html"
output_csv: output/isc_west_2025_exhibitors.csv
request_delay_seconds: 0.25     # minimum gap between requests, shared by all threads
concurrency: 4

rx:                             # optional overrides, everything is auto-discovered
  category_filter_name: "Product Categories"
```

`output_csv` is resolved relative to the project root. Anything under `rx:`
overrides what discovery found, which is the escape hatch if a site changes its
markup.

## Adding another directory

* **Same platform:** copy `config/isc_west_2025.yaml`, change `name`,
  `directory_url` and `output_csv`.
* **Different platform:** subclass `DirectoryAdapter` in
  `expo_scraper/adapters/`, implement `discover()`, `list_exhibitors()` and
  `build_exhibitor()`, and register it in `expo_scraper/adapters/__init__.py`.
  The pipeline, CSV writer and CLI stay the same.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

Tests are offline: they cover the settings parser, the URL slug port, the
listing/detail field mapping and the config loader.

## Project layout

```
expo_scraper/
  cli.py            argparse entry point
  config.py         YAML job config
  pipeline.py       discover -> list -> enrich -> export
  models.py         Exhibitor dataclass + CSV header mapping
  http.py           retrying session + rate limiter
  adapters/
    base.py         adapter contract
    rx_platform.py  RX / Reed Exhibitions directories (Algolia + GraphQL)
  exporters/
    csv_writer.py
config/             one YAML per directory
tests/
output/             results (git-ignored)
```

## Notes

* Only public, unauthenticated endpoints are used, with the same keys the
  public site ships to every visitor.
* Be polite: keep `request_delay_seconds` above zero and `concurrency` small.
