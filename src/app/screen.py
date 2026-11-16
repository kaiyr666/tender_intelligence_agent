"""Run the screening for a date range: fetch, reduce to notices, pre-filter."""

import json
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from app.fetch import FetchResult, fetch_releases
from app.notices import Notice, build_notices
from app.prefilter import Screened, prefilter
from app.profile import Profile, load_profile

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"


@dataclass(frozen=True)
class ScreenResult:
    screened: list[Screened]
    releases_fetched: int
    planning_count: int
    withdrawn_count: int
    complete: bool
    problem: str | None

    @property
    def kept(self) -> list[Notice]:
        return [s.notice for s in self.screened if s.drop_reason is None]

    @property
    def dropped_by_reason(self) -> Counter:
        return Counter(s.drop_reason for s in self.screened if s.drop_reason is not None)


def screen(
    date_from: date,
    date_to: date,
    now: datetime,
    profile: Profile | None = None,
    fetch: Callable[[date, date], FetchResult] = fetch_releases,
) -> ScreenResult:
    """Fetch the range and pre-filter its tender notices against the profile."""
    fetched = fetch(date_from, date_to)
    batch = build_notices(fetched.releases)
    return ScreenResult(
        screened=prefilter(batch.tenders, profile or load_profile(), now),
        releases_fetched=len(fetched.releases),
        planning_count=batch.planning_count,
        withdrawn_count=batch.withdrawn_count,
        complete=fetched.complete,
        problem=fetched.problem,
    )


def last_full_week(today: date) -> tuple[date, date]:
    """Monday to Sunday of the week before the one containing `today`."""
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(days=7), this_monday - timedelta(days=1)


def save_notices(notices: list[Notice], path: Path) -> None:
    """Write the reduced, contact-free notices as JSON (never the raw API data)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [notice.model_dump(mode="json") for notice in notices]
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def format_summary(result: ScreenResult, date_from: date, date_to: date) -> str:
    """Plain-text counts for the terminal."""
    tenders = len(result.screened)
    lines = [
        f"Find a Tender, {date_from} to {date_to}",
        f"  releases fetched:       {result.releases_fetched}",
        f"  tender notices:         {tenders}",
        f"  planning notices:       {result.planning_count} (counted, not screened)",
        f"  withdrawn or cancelled: {result.withdrawn_count}",
        f"  kept by pre-filter:     {len(result.kept)}",
    ]
    for reason, count in result.dropped_by_reason.most_common():
        lines.append(f"  dropped, {reason}: {count}")
    if not result.complete:
        lines.append(f"INCOMPLETE: the fetch stopped early ({result.problem}).")
    return "\n".join(lines)
