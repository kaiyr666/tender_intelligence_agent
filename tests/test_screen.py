"""The screening run end to end on the fixture, with a fake fetch (no network)."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.__main__ import parse_args
from app.fetch import FetchResult
from app.prefilter import LOW_VALUE
from app.screen import format_summary, last_full_week, save_notices, screen

FIXTURE = Path(__file__).parent / "fixtures" / "releases_sample.json"
NOW = datetime(2026, 11, 16, tzinfo=UTC)
WEEK = (date(2026, 11, 9), date(2026, 11, 15))


def fake_fetch(complete=True):
    releases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    problem = None if complete else "HTTP 503 after 5 attempts"
    return lambda date_from, date_to: FetchResult(releases, complete, problem)


def test_screen_counts_every_group():
    result = screen(*WEEK, NOW, fetch=fake_fetch())
    assert (result.releases_fetched, len(result.screened)) == (10, 5)
    assert (result.planning_count, result.withdrawn_count) == (2, 1)


def test_screen_keeps_the_relevant_cleaning_notices():
    result = screen(*WEEK, NOW, fetch=fake_fetch())
    assert {n.notice_id for n in result.kept} == {"108109-2026", "108059-2026"}


def test_summary_shows_drop_reasons():
    result = screen(*WEEK, NOW, fetch=fake_fetch())
    assert f"dropped, {LOW_VALUE}: 1" in format_summary(result, *WEEK)


def test_summary_flags_an_incomplete_fetch():
    result = screen(*WEEK, NOW, fetch=fake_fetch(complete=False))
    assert "INCOMPLETE" in format_summary(result, *WEEK)


def test_saved_notices_contain_no_contact_details(tmp_path):
    result = screen(*WEEK, NOW, fetch=fake_fetch())
    path = tmp_path / "notices.json"
    save_notices([s.notice for s in result.screened], path)
    saved = path.read_text(encoding="utf-8")
    assert "example.org" not in saved and "Jane Example" not in saved


@pytest.mark.parametrize("today", [date(2026, 11, 16), date(2026, 11, 22)])  # Monday, Sunday
def test_last_full_week_is_the_previous_monday_to_sunday(today):
    assert last_full_week(today) == WEEK


def test_cli_defaults_to_the_last_full_week():
    args = parse_args([], today=date(2026, 11, 18))
    assert (args.date_from, args.date_to) == WEEK


def test_cli_rejects_a_range_that_ends_before_it_starts():
    with pytest.raises(SystemExit):
        parse_args(["--from", "2026-11-15", "--to", "2026-11-09"], today=date(2026, 11, 18))
