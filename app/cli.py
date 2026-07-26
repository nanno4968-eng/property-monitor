"""CLI entry point: `python -m app.cli run` (also used by GitHub Actions)."""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(prog="property-monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Run the full pipeline once: collect, parse, score, report, email.")
    sub.add_parser("init-db", help="Create database tables without running the pipeline.")
    sub.add_parser("watch-reminder", help="Email a reminder with direct search links for the configured watch areas.")
    args = parser.parse_args()

    if args.command == "init-db":
        from app.db import init_db
        init_db()
        print("Database initialised.")
    elif args.command == "run":
        from app.pipeline import run_pipeline
        summary = run_pipeline()
        print(summary)
    elif args.command == "watch-reminder":
        from app.services.area_watch import send_watch_reminder
        send_watch_reminder()


if __name__ == "__main__":
    sys.exit(main())
