"""The web view (slice 8): one self-contained HTML page rendered from a saved run record.

Every test renders from the slice 6 fixture, changed with model_copy where a case needs it.
No LLM, no network: the page is built from the run record alone.
"""

import html
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import html_report
from app.html_report import FIND_A_TENDER_NOTICE, LICENCE_URL, main, render_html, write_html
from app.runs import RedFlagRecord, load_run

FIXTURE = Path(__file__).parent / "fixtures" / "runs" / "2026-11-09_2026-11-15.json"
GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
TOP = "100002-2026"  # rank 1, two lots, a TUPE flag
SECOND = "100001-2026"  # rank 2, whole notice
REJECTED = "100003-2026"
FIND_A_TENDER_HOME = "https://www.find-tender.service.gov.uk"
PAYLOAD = '<script>alert(1)</script>"'
RAW_SCRIPT = "<script>alert(1)</script>"
ESCAPED_SCRIPT = "&lt;script&gt;alert(1)&lt;/script&gt;"
GROUP_LABELS = {
    "shortlisted": "Shortlisted",
    "rejected": "Rejected",
    "needs review": "Needs review",
    "not processed": "Not processed",
}


def fixture_record():
    return load_run(FIXTURE)


def notice(record, notice_id):
    return next(n for n in record.notices if n.notice_id == notice_id)


def with_notice(record, notice_id, **updates):
    notices = [
        n.model_copy(update=updates) if n.notice_id == notice_id else n for n in record.notices
    ]
    return record.model_copy(update={"notices": notices})


def with_lot(record, notice_id, lot_id, **updates):
    lots = [
        lot.model_copy(update=updates) if lot.lot_id == lot_id else lot
        for lot in notice(record, notice_id).lots
    ]
    return with_notice(record, notice_id, lots=lots)


def processed_only(record):
    """The fixture without its not-processed notice: a run with nothing wrong."""
    notices = [n for n in record.notices if n.outcome != "not processed"]
    return record.model_copy(update={"notices": notices})


def hrefs(page):
    return [html.unescape(value) for value in re.findall(r'href="([^"]*)"', page)]


def check_golden(name, actual):
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="")
    assert actual == path.read_text(encoding="utf-8")


# The whole page


def test_page_matches_golden_file():
    check_golden("report.html", render_html(fixture_record()))


def test_page_is_an_html5_document_in_english_for_small_screens():
    page = render_html(fixture_record())

    assert page.lower().startswith("<!doctype html>")
    assert '<html lang="en"' in page
    assert '<meta name="viewport"' in page


def test_page_loads_nothing_from_outside():
    page = render_html(fixture_record())

    assert page.lower().count("<script") == 1
    assert "src=" not in page.lower()
    assert "@import" not in page
    assert "url(" not in page


def test_page_script_never_uses_inner_html():
    assert "innerHTML" not in render_html(fixture_record())


def test_page_has_a_dark_scheme_and_a_print_style():
    page = render_html(fixture_record())

    assert "prefers-color-scheme" in page
    assert "@media print" in page


def test_rendering_twice_gives_the_same_page():
    record = fixture_record()

    assert render_html(record) == render_html(record)


def test_rendering_writes_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(html_report, "OUTPUT_DIR", tmp_path / "output")

    render_html(fixture_record())

    assert list(tmp_path.iterdir()) == []


# Escaping untrusted text


def payload_in_criterion_reason(record):
    best = notice(record, TOP).lots[0]
    criteria = [best.criteria[0].model_copy(update={"reason": PAYLOAD}), *best.criteria[1:]]
    return with_lot(record, TOP, best.lot_id, criteria=criteria)


# Text the plan says the page shows.
SHOWN_TEXT = {
    "title": lambda r: with_notice(r, TOP, title=PAYLOAD),
    "buyer": lambda r: with_notice(r, TOP, buyer=PAYLOAD),
    "rationale": lambda r: with_notice(r, TOP, rationale=PAYLOAD),
    "best lot name": lambda r: with_lot(r, TOP, "1", lot_name=PAYLOAD),
    "other lot reason": lambda r: with_lot(r, TOP, "2", reasons=[PAYLOAD]),
    "criterion reason": payload_in_criterion_reason,
    "notice reason": lambda r: with_notice(r, REJECTED, reason=PAYLOAD),
}
# Text the page may or may not show; either way it must never come out raw.
OTHER_TEXT = {
    "description": lambda r: with_notice(r, TOP, description=PAYLOAD),
    "red-flag quote": lambda r: with_notice(
        r, TOP, red_flags=[RedFlagRecord(kind="tupe", quote=PAYLOAD)]
    ),
}
ALL_TEXT = {**SHOWN_TEXT, **OTHER_TEXT}


@pytest.mark.parametrize("insert_payload", list(ALL_TEXT.values()), ids=list(ALL_TEXT))
def test_a_script_tag_in_untrusted_text_never_comes_out_raw(insert_payload):
    page = render_html(insert_payload(fixture_record()))

    assert RAW_SCRIPT not in page
    assert page.lower().count("<script") == 1


@pytest.mark.parametrize("insert_payload", list(SHOWN_TEXT.values()), ids=list(SHOWN_TEXT))
def test_a_script_tag_in_shown_text_comes_out_escaped(insert_payload):
    page = render_html(insert_payload(fixture_record()))

    assert ESCAPED_SCRIPT in page


def test_quotes_in_a_title_are_escaped():
    page = render_html(fixture_record())

    assert "=HYPERLINK(&quot;x&quot;) Cleaning | Leeds offices" in page
    assert '=HYPERLINK("x")' not in page


def test_html_in_a_rationale_is_escaped():
    page = render_html(fixture_record())

    assert "<b>Value</b>" not in page
    assert "&lt;b&gt;Value&lt;/b&gt;" in page


# Links


def allowed_links(record):
    allowed = {LICENCE_URL, FIND_A_TENDER_HOME, FIND_A_TENDER_HOME + "/"}
    for n in record.notices:
        allowed |= {n.url, FIND_A_TENDER_NOTICE + n.notice_id}
    return allowed


def test_every_link_is_in_page_a_notice_page_or_the_licence():
    record = fixture_record()
    page = render_html(record)

    links = hrefs(page)

    assert page.count("href=") == len(links)  # every href is double-quoted, so none is missed
    assert LICENCE_URL in links
    outside = [link for link in links if not link.startswith("#")]
    assert [link for link in outside if link not in allowed_links(record)] == []


def test_each_shortlisted_card_links_to_its_notice_on_find_a_tender():
    record = fixture_record()
    page = render_html(record)

    shortlisted = [n for n in record.notices if n.outcome == "shortlisted"]
    assert page.count("Open on Find a Tender") >= len(shortlisted)
    assert all(n.url in hrefs(page) for n in shortlisted)


def test_a_javascript_url_is_not_rendered_as_a_link():
    record = with_notice(fixture_record(), TOP, url="javascript:alert(1)")

    links = hrefs(render_html(record))

    assert not any("javascript:" in link.lower() for link in links)
    assert FIND_A_TENDER_NOTICE + TOP in links


@pytest.mark.parametrize(
    "url",
    [
        "JavaScript:alert(1)",
        "http://example.com/x",
        "//example.com/x",
        "data:text/html,x",
        "https://[2001:db8::1/tender",  # malformed: urlsplit raises ValueError
    ],
)
def test_a_notice_url_that_is_not_https_falls_back_to_its_find_a_tender_page(url):
    record = with_notice(fixture_record(), TOP, url=url)

    links = hrefs(render_html(record))

    assert url not in links
    assert FIND_A_TENDER_NOTICE + TOP in links


def test_a_quote_in_a_url_cannot_add_an_attribute():
    record = with_notice(fixture_record(), TOP, url='https://example.com/a" onmouseover="alert(1)')

    page = render_html(record)

    assert ' onmouseover="' not in page


# Run health


def test_a_run_with_nothing_wrong_has_no_incomplete_banner():
    record = processed_only(fixture_record())
    assert record.incomplete_reasons == []

    assert "INCOMPLETE" not in render_html(record)


def test_a_not_processed_notice_shows_the_incomplete_banner():
    record = fixture_record()
    assert record.complete and record.incomplete_reasons

    page = render_html(record)

    assert "INCOMPLETE" in page
    assert all(html.escape(reason) in page for reason in record.incomplete_reasons)


def test_a_stopped_fetch_shows_the_incomplete_banner_with_the_problem():
    record = processed_only(fixture_record()).model_copy(
        update={"complete": False, "problem": "HTTP 503"}
    )

    page = render_html(record)

    assert "INCOMPLETE" in page
    assert "HTTP 503" in page
    assert all(html.escape(reason) in page for reason in record.incomplete_reasons)


# Deadlines and days left


@pytest.mark.parametrize(
    ("generated_at", "label"),
    [
        (datetime(2026, 11, 16, 9, 30, tzinfo=UTC), "18 days left"),
        (datetime(2026, 11, 16, 23, 30, tzinfo=UTC), "18 days left"),  # by date, not hours
        # 23:30 UTC on 16 Nov, though the local date is 17 Nov: days count by UTC date.
        (datetime(2026, 11, 17, 0, 30, tzinfo=timezone(timedelta(hours=1))), "18 days left"),
        (datetime(2026, 12, 3, 9, 0, tzinfo=UTC), "1 day left"),
        (datetime(2026, 12, 4, 8, 0, tzinfo=UTC), "closes today"),
    ],
)
def test_days_left_are_counted_from_generated_at(generated_at, label):
    record = fixture_record().model_copy(update={"generated_at": generated_at})

    assert label in render_html(record)


def test_a_deadline_before_generated_at_shows_closed():
    record = fixture_record().model_copy(
        update={"generated_at": datetime(2026, 12, 5, 8, 0, tzinfo=UTC)}
    )

    page = render_html(record)

    assert "closed" in page
    assert "days left" not in page
    assert "day left" not in page
    assert "closes today" not in page


def test_the_deadline_is_shown_in_utc():
    assert "2026-12-04 12:00 UTC" in render_html(fixture_record())


def test_a_deadline_with_another_offset_is_converted_to_utc():
    deadline = datetime(2026, 12, 4, 12, 0, tzinfo=timezone(timedelta(hours=1)))
    record = with_notice(fixture_record(), TOP, deadline=deadline)

    assert "2026-12-04 11:00 UTC" in render_html(record)


def test_a_shortlisted_notice_with_no_deadline_says_not_stated():
    record = fixture_record()
    before = render_html(record).lower().count("not stated")

    page = render_html(with_notice(record, SECOND, deadline=None))

    assert page.lower().count("not stated") > before


# Shortlist cards


def test_shortlist_cards_are_in_rank_order():
    page = render_html(fixture_record())

    assert page.index("Leeds offices") < page.index("Security guarding, Hull")


def test_shortlist_cards_follow_rank_not_list_order():
    record = fixture_record()
    reordered = record.model_copy(update={"notices": list(reversed(record.notices))})

    page = render_html(reordered)

    assert page.index("Leeds offices") < page.index("Security guarding, Hull")


def test_a_card_shows_its_score_to_two_decimals():
    record = with_notice(fixture_record(), SECOND, score=0.876)

    assert "0.88" in render_html(record)


def test_the_threshold_is_shown():
    assert "0.60" in render_html(fixture_record())


def test_the_threshold_comes_from_the_run_profile():
    record = fixture_record()
    profile = record.profile.model_copy(update={"shortlist_threshold": 0.65})

    assert "0.65" in render_html(record.model_copy(update={"profile": profile}))


def test_a_card_shows_the_best_lot_of_a_multi_lot_notice():
    page = render_html(fixture_record())

    assert "Lot 1: Offices | north" in page


def test_a_red_flag_shows_as_a_chip_label():
    flag = RedFlagRecord(kind="tupe", quote="staff will transfer")
    record = with_notice(fixture_record(), TOP, rationale=None, red_flags=[flag])

    assert "TUPE" in render_html(record)


def test_a_card_shows_buyer_and_rationale():
    page = render_html(fixture_record())

    assert "Buyer 2" in page
    assert "Office cleaning in Leeds | in the value band. TUPE applies." in page


# Breakdown


def test_breakdown_shows_each_criterion_with_weight_score_and_reason():
    record = fixture_record()
    best = notice(record, TOP).lots[0]

    page = render_html(record)

    for criterion in best.criteria:
        assert criterion.name in page.lower()
        assert f"{criterion.weight:.2f}" in page
        assert f"{criterion.score:.2f}" in page
        assert html.escape(criterion.reason) in page


def test_breakdown_shows_the_other_lots_with_status_and_reasons():
    page = render_html(fixture_record())

    assert "Lot 2: Wards" in page
    assert "gated" in page.lower()
    assert "main service is clinical cleaning" in page


def test_each_shortlisted_card_has_a_details_breakdown():
    record = fixture_record()
    shortlisted = [n for n in record.notices if n.outcome == "shortlisted"]

    assert render_html(record).count("<details") >= len(shortlisted)


# Other groups


def test_each_group_heading_shows_its_count():
    record = fixture_record()
    counts = Counter(n.outcome for n in record.notices)

    page = render_html(record)

    for outcome, label in GROUP_LABELS.items():
        assert f"{label} ({counts[outcome]})" in page


def test_other_groups_list_each_notice_with_its_title_and_reason():
    record = fixture_record()

    page = render_html(record)

    for n in record.notices:
        if n.outcome != "shortlisted":
            assert n.notice_id in page
            assert html.escape(n.title) in page
            assert html.escape(n.reason) in page


def test_a_run_with_no_notices_renders_every_group_empty():
    record = fixture_record().model_copy(update={"notices": []})

    page = render_html(record)

    assert page.count("None this week.") == 4
    assert "Shortlisted (0)" in page


# Funnel, profile, header and footer


def test_funnel_shows_the_counts_and_the_cost():
    record = fixture_record().model_copy(update={"prefilter_kept": 87, "planning_count": 39})

    page = render_html(record)

    assert "463" in page
    assert "87" in page
    assert "39" in page
    assert "$0.04" in page


def test_profile_section_shows_what_we_screen_for():
    record = fixture_record()
    profile = record.profile

    page = render_html(record)

    assert "What we screen for" in page
    for service in profile.offered_services + profile.excluded_services:
        assert html.escape(service.name) in page
    assert "£100,000" in page
    assert "£5,000,000" in page
    assert all(html.escape(held) in page for held in profile.accreditations_held)
    assert f"{profile.shortlist_threshold:.2f}" in page


def test_profile_value_band_comes_from_the_run_profile():
    record = fixture_record()
    profile = record.profile.model_copy(update={"value_max_gbp": 4_500_000.0})

    assert "£4,500,000" in render_html(record.model_copy(update={"profile": profile}))


def test_footer_gives_the_licence_and_says_where_scores_come_from():
    page = render_html(fixture_record())

    assert "Open Government Licence v3.0" in page
    assert "Scores come from code; the LLM only reads notices and writes the rationale." in page


def test_header_shows_the_week_the_generated_time_and_the_model():
    page = render_html(fixture_record())

    assert "2026-11-09" in page
    assert "2026-11-15" in page
    assert "2026-11-16 09:30 UTC" in page
    assert "test-model" in page


# Writing the file and the command line


def test_write_html_writes_the_rendered_page_into_a_new_folder(tmp_path):
    record = fixture_record()
    path = tmp_path / "a" / "b" / "report.html"

    written = write_html(record, path)

    assert written == path
    assert path.read_text(encoding="utf-8") == render_html(record)


def test_main_writes_to_the_out_path_and_prints_it(tmp_path, capsys):
    out = tmp_path / "views" / "week.html"

    main([str(FIXTURE), "--out", str(out)])

    assert out.read_text(encoding="utf-8") == render_html(fixture_record())
    assert str(out) in capsys.readouterr().out


def test_main_without_out_writes_report_for_the_run_id(tmp_path, monkeypatch):
    monkeypatch.setattr(html_report, "OUTPUT_DIR", tmp_path / "output")

    main([str(FIXTURE)])

    expected = tmp_path / "output" / "report_2026-11-09_2026-11-15.html"
    assert expected.read_text(encoding="utf-8") == render_html(fixture_record())


@pytest.mark.parametrize("contents", ["{not json", None], ids=["broken JSON", "missing file"])
def test_main_on_an_unloadable_run_file_exits_naming_the_file(tmp_path, monkeypatch, contents):
    monkeypatch.setattr(html_report, "OUTPUT_DIR", tmp_path / "output")
    path = tmp_path / "2026-11-09_2026-11-15.json"
    if contents is not None:
        path.write_text(contents, encoding="utf-8")

    with pytest.raises(SystemExit) as stopped:
        main([str(path)])

    assert stopped.value.code not in (0, None)
    assert path.name in str(stopped.value.code)
    assert not (tmp_path / "output").exists()


def test_rendering_a_run_does_not_load_the_pipeline():
    # The web view reads only the run record: no extractor, llm.py or settings, which load .env
    # (PLAN, rules for slices 6-9).
    code = (
        "import sys; from pathlib import Path; from app.html_report import render_html; "
        f"from app.runs import load_run; render_html(load_run(Path({str(FIXTURE)!r}))); "
        "print(','.join(sorted(m for m in sys.modules if m.startswith('app.') or m == 'dotenv')))"
    )

    loaded = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()

    assert loaded.split(",") == ["app.html_report", "app.runs"]
