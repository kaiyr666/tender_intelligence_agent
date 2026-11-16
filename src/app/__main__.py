"""Command line entry point.

uv run python -m app                                # last full Monday-Sunday week
uv run python -m app --from 2026-11-09 --to 2026-11-15
"""

import argparse
import sys
from datetime import UTC, date, datetime

from app.fetch import FetchError
from app.screen import DATA_DIR, format_summary, last_full_week, save_notices, screen


def parse_args(argv: list[str], today: date) -> argparse.Namespace:
    default_from, default_to = last_full_week(today)
    parser = argparse.ArgumentParser(prog="app", description="Screen UK public tenders.")
    parser.add_argument("--from", dest="date_from", type=date.fromisoformat, default=default_from)
    parser.add_argument("--to", dest="date_to", type=date.fromisoformat, default=default_to)
    args = parser.parse_args(argv)
    if args.date_from > args.date_to:
        parser.error("--from must not be after --to")
    return args


def main() -> None:
    now = datetime.now(UTC)
    args = parse_args(sys.argv[1:], now.date())
    try:
        result = screen(args.date_from, args.date_to, now)
    except FetchError as error:
        sys.exit(f"Could not fetch tenders: {error}")
    save_notices(
        [s.notice for s in result.screened],
        DATA_DIR / f"notices_{args.date_from}_{args.date_to}.json",
    )
    print(format_summary(result, args.date_from, args.date_to))


if __name__ == "__main__":
    main()
