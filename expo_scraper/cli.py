"""Command-line entry point: `python -m expo_scraper --config config/isc_west_2025.yaml`."""

from __future__ import annotations

import argparse
import logging
import sys

from expo_scraper import __version__
from expo_scraper.config import ConfigError, ScrapeConfig
from expo_scraper.pipeline import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="expo-scraper",
        description="Scrape a trade-show exhibitor directory into a CSV.",
    )
    parser.add_argument("-c", "--config", action="append", required=True, metavar="YAML",
                        help="job config file (repeatable to run several directories)")
    parser.add_argument("-o", "--output", metavar="CSV",
                        help="override output_csv from the config (single --config only)")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="only process the first N exhibitors (smoke test)")
    parser.add_argument("--concurrency", type=int, metavar="N",
                        help="override concurrency from the config")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not args.verbose:
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    if args.output and len(args.config) > 1:
        print("--output can only be used with a single --config", file=sys.stderr)
        return 2

    exit_code = 0
    for path in args.config:
        try:
            config = ScrapeConfig.from_yaml(path)
            summary = run(config, output_override=args.output, limit=args.limit,
                          concurrency=args.concurrency)
        except ConfigError as exc:
            print(f"config error: {exc}", file=sys.stderr)
            exit_code = 2
            continue
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).exception("run failed for %s: %s", path, exc)
            exit_code = 1
            continue
        print(summary.pretty())
    return exit_code
