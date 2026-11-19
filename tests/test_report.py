"""The weekly report and CSV, from a fixed scored input (no scoring, no LLM)."""

import csv
import io
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.extract import Extraction, RedFlag
from app.notices import Notice
from app.report import RunSummary, render_csv, render_report, write_report
from app.score import (
    ELIGIBLE,
    GATED,
    NEEDS_REVIEW,
    NOT_PROCESSED,
    REJECTED,
    SHORTLISTED,
    Criterion,
    LotResult,
    NoticeResult,
)

GOLDEN_DIR = Path(__file__).parent / "fixtures" / "golden"
WEIGHTS = {
    "service": 0.35,
    "region": 0.2,
    "value": 0.15,
    "accreditations": 0.1,
    "mobilisation": 0.1,
    "deadline": 0.1,
}
RUN = RunSummary(
    date_from=date(2026, 11, 9),
    date_to=date(2026, 11, 15),
    generated_at=datetime(2026, 11, 16, 9, 30, tzinfo=UTC),
    tender_count=463,
    prefilter_kept=5,
    planning_count=12,
    complete=True,
    problem=None,
    llm_calls=7,
    cost_usd=0.0412,
    threshold=0.6,
    weights=WEIGHTS,
)


def notice(number, title, value=250_000, deadline=datetime(2026, 12, 4, 12, tzinfo=UTC)):
    notice_id = f"10000{number}-2026"
    return Notice(
        ocid=f"ocds-test-{number}",
        notice_id=notice_id,
        published=datetime(2026, 11, 12, tzinfo=UTC),
        title=title,
        description="Not shown in the report.",
        buyer=f"Buyer {number}",
        status="active",
        main_category="services",
        value_gbp=value,
        deadline=deadline,
        url=f"https://www.find-tender.service.gov.uk/Notice/{notice_id}",
        cpv_codes=["90910000"],
        regions=[],
        lots=[],
    )


def criteria(value_score=1.0, value_reason="£250,000 is in the value band"):
    return [
        Criterion("service", 1.0, "main service is office and commercial cleaning"),
        Criterion("region", 1.0, "in region (UKE, from delivery address)"),
        Criterion("value", value_score, value_reason),
        Criterion("accreditations", 1.0, "no preferred accreditations listed"),
        Criterion("mobilisation", 0.5, "mobilisation time not stated"),
        Criterion("deadline", 1.0, "18 days to respond (needs 14)"),
    ]


def lot(lot_id, name, score, status=ELIGIBLE, reasons=(), **criteria_args):
    return LotResult(lot_id, name, status, list(reasons), criteria(**criteria_args), score)


def extraction(red_flags=()):
    return Extraction(
        notice_mandatory_accreditations=[],
        notice_preferred_accreditations=[],
        red_flags=list(red_flags),
        lots=[
            {
                "lot_id": "whole",
                "services": [],
                "primary_service": None,
                "primary_service_quote": None,
                "region_nuts1": [],
                "contract_length_months": None,
                "mobilisation_weeks": None,
                "mandatory_accreditations": [],
                "preferred_accreditations": [],
            }
        ],
    )


def scored_results():
    """Two shortlisted (lower score first, to check ranking), one of each other group."""
    over_band = "£6,000,000 is over £5,000,000"
    second = lot("whole", "whole notice", 0.85, value_score=0.3, value_reason=over_band)
    best = lot("1", "Lot 1: Offices | north", 0.95)
    clinical = lot("2", "Lot 2: Wards", 0.4, GATED, ["main service is clinical cleaning"])
    tupe = RedFlag(kind="tupe", quote="TUPE applies")
    gated = lot("whole", "whole notice", 0.6, GATED, ["requires CHAS"])
    return [
        NoticeResult(
            notice(1, "Security guarding, Hull", value=6_000_000),
            SHORTLISTED,
            "whole notice scores 0.85 (threshold 0.60)",
            second,
            [second],
            extraction(),
        ),
        NoticeResult(
            notice(2, '=HYPERLINK("x") Cleaning | Leeds offices'),
            SHORTLISTED,
            "Lot 1: Offices | north scores 0.95 (threshold 0.60)",
            best,
            [best, clinical],
            extraction([tupe]),
        ),
        NoticeResult(
            notice(3, "Maintenance framework", value=None, deadline=None),
            REJECTED,
            "requires CHAS, which the company does not hold",
            None,
            [gated],
            extraction(),
        ),
        NoticeResult(
            notice(4, "Hospital cleaning"),
            NEEDS_REVIEW,
            "the extraction failed: the model did not return valid output",
            None,
            [],
            None,
        ),
        NoticeResult(
            notice(5, "Caretaking"),
            NOT_PROCESSED,
            "the LLM budget was reached before this notice",
            None,
            [],
            None,
        ),
    ]


RATIONALES = {
    "100001-2026": "Guarding in Hull, in region. <b>Value</b> is over the band.",
    "100002-2026": "Office cleaning in Leeds | in the value band. TUPE applies.",
}


def check_golden(name, actual):
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8", newline="")
    assert actual == path.read_text(encoding="utf-8")


def test_report_matches_golden_file():
    check_golden("report.md", render_report(scored_results(), RATIONALES, RUN))


def test_csv_matches_golden_file():
    check_golden("shortlist.csv", render_csv(scored_results(), RATIONALES))


def test_shortlist_is_ranked_by_score():
    report = render_report(scored_results(), RATIONALES, RUN)

    assert report.index("Leeds offices") < report.index("Security guarding, Hull")


def test_report_has_the_four_groups_with_counts():
    report = render_report(scored_results(), RATIONALES, RUN)

    for heading in (
        "## Shortlisted (2)",
        "## Rejected after extraction (1)",
        "## Needs review (1)",
        "## Not processed (1)",
    ):
        assert heading in report


def test_report_shows_planning_count_cost_and_attribution():
    report = render_report(scored_results(), RATIONALES, RUN)

    assert "12 planning-stage notices" in report
    assert "$0.04" in report
    assert "Open Government Licence v3.0" in report


def test_incomplete_banner_only_when_the_fetch_stopped():
    stopped = replace(RUN, complete=False, problem="HTTP 503 after 3 attempts")

    assert "INCOMPLETE" not in render_report(scored_results(), RATIONALES, RUN)
    assert "INCOMPLETE" in render_report(scored_results(), RATIONALES, stopped)
    assert "HTTP 503 after 3 attempts" in render_report(scored_results(), RATIONALES, stopped)


def test_empty_groups_still_render():
    report = render_report([], {}, RUN)

    assert "## Shortlisted (0)" in report
    assert "None this week." in report


def test_html_in_third_party_text_is_escaped():
    report = render_report(scored_results(), RATIONALES, RUN)

    assert "<b>" not in report
    assert "&lt;b&gt;" in report


def test_pipes_in_table_cells_are_escaped():
    report = render_report(scored_results(), RATIONALES, RUN)

    assert "Lot 1: Offices \\| north" in report


def test_csv_neutralises_spreadsheet_formulas():
    rows = list(csv.DictReader(io.StringIO(render_csv(scored_results(), RATIONALES))))

    titles = [row["title"] for row in rows]
    assert '\'=HYPERLINK("x") Cleaning | Leeds offices' in titles


def test_csv_has_one_row_per_assessed_notice_with_its_outcome():
    rows = list(csv.DictReader(io.StringIO(render_csv(scored_results(), RATIONALES))))

    assert [row["outcome"] for row in rows] == [
        SHORTLISTED,
        SHORTLISTED,
        REJECTED,
        NEEDS_REVIEW,
        NOT_PROCESSED,
    ]
    assert rows[0]["notice_id"] == "100002-2026"


def test_write_report_creates_both_files(tmp_path):
    report_path, csv_path = write_report(scored_results(), RATIONALES, RUN, tmp_path / "out")

    assert report_path.read_text(encoding="utf-8").startswith("# Tender shortlist")
    # Excel needs the byte-order mark to read "£" correctly.
    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")


@pytest.mark.parametrize("value", ["+1", "-1", "@SUM(A1)", "\t=1"])
def test_csv_cells_starting_with_formula_characters_are_prefixed(value):
    result = scored_results()[0]
    result = replace(result, notice=result.notice.model_copy(update={"title": value}))

    rows = list(csv.DictReader(io.StringIO(render_csv([result], {}))))

    assert rows[0]["title"] == "'" + value
