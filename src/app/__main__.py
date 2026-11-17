"""Command line entry point.

uv run python -m app                                # last full Monday-Sunday week
uv run python -m app --from 2026-11-09 --to 2026-11-15
"""

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from app.assess import assess, format_assessment
from app.config import get_settings
from app.explain import write_rationales
from app.extract import ExtractionCache
from app.fetch import FetchError
from app.llm import ProviderError, Usage, get_provider
from app.profile import load_profile
from app.report import RunSummary, write_report
from app.screen import DATA_DIR, format_summary, last_full_week, save_notices, screen

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "extractions"


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
    # Tender titles contain "£" and dashes, which a Windows console code page cannot print.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    now = datetime.now(UTC)
    args = parse_args(sys.argv[1:], now.date())
    try:
        settings = get_settings()  # fail on bad LLM settings before the 3-minute fetch
    except RuntimeError as error:
        sys.exit(f"LLM settings: {error}")
    profile = load_profile()
    try:
        result = screen(args.date_from, args.date_to, now, profile)
    except FetchError as error:
        sys.exit(f"Could not fetch tenders: {error}")
    save_notices(
        [s.notice for s in result.screened],
        DATA_DIR / f"notices_{args.date_from}_{args.date_to}.json",
    )
    print(format_summary(result, args.date_from, args.date_to))

    usage = Usage(budget_usd=settings.budget_usd)
    try:
        results = assess(
            result.kept, profile, now, get_provider(), usage, ExtractionCache(CACHE_DIR)
        )
    except ProviderError as error:
        sys.exit(f"{error}\nExtractions done so far are cached; run again to continue.")
    print(format_assessment(results, usage))

    rationales = write_rationales(results, get_provider(), usage)
    run = RunSummary(
        date_from=args.date_from,
        date_to=args.date_to,
        generated_at=now,
        tender_count=len(result.screened),
        prefilter_kept=len(result.kept),
        planning_count=result.planning_count,
        complete=result.complete,
        problem=result.problem,
        llm_calls=usage.calls,
        cost_usd=usage.cost_usd,
        threshold=profile.scoring.shortlist_threshold,
        weights=profile.scoring.weights.model_dump(),
    )
    report_path, csv_path = write_report(results, rationales, run)
    print(f"Report: {report_path}\nCSV:    {csv_path}  (LLM cost in total ${usage.cost_usd:.2f})")


if __name__ == "__main__":
    main()
