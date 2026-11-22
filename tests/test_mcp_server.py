"""The read-only MCP server over saved run records (slice 7).

The tools are plain functions over a runs folder, so most tests call them directly;
two tests go through the protocol, in memory and over real stdio.
"""

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import anyio
import pytest
from mcp import Client, StdioServerParameters
from mcp.server.mcpserver.exceptions import ToolError

from app import mcp_server
from app.mcp_server import (
    DESCRIPTION_CAP,
    build_server,
    get_profile,
    get_tender,
    list_runs,
    search_tenders,
    shortlist,
)
from app.runs import load_run, run_id_for, save_run

FIXTURE = Path(__file__).parent / "fixtures" / "runs" / "2026-11-09_2026-11-15.json"
NEWEST = "2026-11-09_2026-11-15"
OLDER = "2026-11-02_2026-11-08"
TOOL_NAMES = {"list_runs", "shortlist", "get_tender", "search_tenders", "get_profile"}


@pytest.fixture
def runs_dir(tmp_path):
    """A runs folder holding a copy of the slice 6 fixture."""
    folder = tmp_path / "runs"
    folder.mkdir()
    shutil.copy(FIXTURE, folder / FIXTURE.name)
    return folder


def fixture_record():
    return load_run(FIXTURE)


def save_older_run(runs_dir, **updates):
    """Save the fixture as the week before, with any fields changed."""
    record = fixture_record().model_copy(
        update={
            "date_from": date(2026, 11, 2),
            "date_to": date(2026, 11, 8),
            "run_id": run_id_for(date(2026, 11, 2), date(2026, 11, 8)),
            **updates,
        }
    )
    return save_run(record, runs_dir)


def save_with_notice(runs_dir, notice_id, **updates):
    """Rewrite the fixture run with one notice's fields changed."""
    record = fixture_record()
    notices = [
        notice.model_copy(update=updates) if notice.notice_id == notice_id else notice
        for notice in record.notices
    ]
    save_run(record.model_copy(update={"notices": notices}), runs_dir)


# list_runs


def test_list_runs_describes_each_run_newest_first(runs_dir):
    save_older_run(runs_dir)

    runs = list_runs(runs_dir)["runs"]

    assert [run["run_id"] for run in runs] == [NEWEST, OLDER]


def test_list_runs_gives_dates_health_counts_and_cost(runs_dir):
    record = fixture_record()

    (run,) = list_runs(runs_dir)["runs"]

    assert run == {
        "run_id": NEWEST,
        "date_from": "2026-11-09",
        "date_to": "2026-11-15",
        "generated_at": "2026-11-16T09:30:00Z",
        "complete": False,
        "incomplete_reasons": record.incomplete_reasons,
        "tender_count": 463,
        "prefilter_kept": 5,
        "planning_count": 12,
        "outcomes": {"shortlisted": 2, "rejected": 1, "needs review": 1, "not processed": 1},
        "llm_cost_usd": 0.0412,
    }


def test_a_run_with_nothing_wrong_is_complete(runs_dir):
    record = fixture_record()
    processed = [n for n in record.notices if n.outcome != "not processed"]
    save_run(record.model_copy(update={"notices": processed}), runs_dir)

    (run,) = list_runs(runs_dir)["runs"]

    assert run["complete"] is True
    assert run["incomplete_reasons"] == []


# shortlist


def test_shortlist_lists_the_shortlisted_notices_in_rank_order(runs_dir):
    result = shortlist(runs_dir)

    assert [row["notice_id"] for row in result["notices"]] == ["100002-2026", "100001-2026"]
    assert [row["rank"] for row in result["notices"]] == [1, 2]


def test_shortlist_row_carries_what_the_bid_team_needs(runs_dir):
    top = shortlist(runs_dir)["notices"][0]

    assert top == {
        "rank": 1,
        "notice_id": "100002-2026",
        "title": '=HYPERLINK("x") Cleaning | Leeds offices',
        "buyer": "Buyer 2",
        "score": 0.95,
        "best_lot": "Lot 1: Offices | north",
        "deadline": "2026-12-04T12:00:00Z",
        "value_gbp": 250000.0,
        "red_flags": [{"kind": "tupe", "quote": "TUPE applies"}],
        "rationale": "Office cleaning in Leeds | in the value band. TUPE applies.",
        "url": "https://www.find-tender.service.gov.uk/Notice/100002-2026",
    }


def test_shortlist_gives_the_threshold_and_run_health(runs_dir):
    result = shortlist(runs_dir)

    assert result["run_id"] == NEWEST
    assert result["generated_at"] == "2026-11-16T09:30:00Z"
    assert result["threshold"] == 0.6
    assert result["incomplete_reasons"] == fixture_record().incomplete_reasons


def test_the_newest_run_is_the_default(runs_dir):
    save_older_run(runs_dir, notices=[])

    assert shortlist(runs_dir)["run_id"] == NEWEST
    assert shortlist(runs_dir, run_id=OLDER)["notices"] == []


# get_tender


def test_get_tender_returns_the_full_notice_record(runs_dir):
    notice = next(n for n in fixture_record().notices if n.notice_id == "100002-2026")

    result = get_tender(runs_dir, "100002-2026")

    assert result["run_id"] == NEWEST
    assert result["outcome"] == "shortlisted"
    assert result["reason"] == notice.reason
    assert result["lots"] == [lot.model_dump(mode="json") for lot in notice.lots]
    assert result["red_flags"] == [{"kind": "tupe", "quote": "TUPE applies"}]
    assert result["rationale"] == notice.rationale
    assert result["url"] == notice.url
    assert result["description"] == notice.description
    assert result["description_cut"] is False


def test_get_tender_explains_a_rejection(runs_dir):
    result = get_tender(runs_dir, "100003-2026")

    assert result["outcome"] == "rejected"
    assert result["reason"] == "requires CHAS, which the company does not hold"
    assert result["rationale"] is None


def test_a_long_description_is_cut_with_a_marker(runs_dir):
    save_with_notice(runs_dir, "100001-2026", description="a" * (DESCRIPTION_CAP + 500))

    result = get_tender(runs_dir, "100001-2026")

    assert DESCRIPTION_CAP == 4000
    assert result["description"].startswith("a" * DESCRIPTION_CAP)
    assert "a" * (DESCRIPTION_CAP + 1) not in result["description"]
    assert "cut" in result["description"][DESCRIPTION_CAP:]
    assert result["description_cut"] is True


def test_a_description_of_exactly_the_cap_is_not_cut(runs_dir):
    save_with_notice(runs_dir, "100001-2026", description="a" * DESCRIPTION_CAP)

    result = get_tender(runs_dir, "100001-2026")

    assert result["description"] == "a" * DESCRIPTION_CAP
    assert result["description_cut"] is False


def test_a_notice_without_a_description_has_none(runs_dir):
    save_with_notice(runs_dir, "100001-2026", description=None)

    result = get_tender(runs_dir, "100001-2026")

    assert result["description"] is None
    assert result["description_cut"] is False


def test_an_unknown_notice_says_the_prefilter_may_have_dropped_it(runs_dir):
    with pytest.raises(ToolError, match="pre-filter"):
        get_tender(runs_dir, "999999-2026")


# search_tenders


def ids(result):
    return [row["notice_id"] for row in result["notices"]]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("hull", ["100001-2026"]),  # title
        ("BUYER 3", ["100003-2026"]),  # buyer, any case
        ("wards", ["100002-2026"]),  # lot name
        ("chas", ["100003-2026"]),  # reason
        ("guarding hull", ["100001-2026"]),  # every word, anywhere
        ("hull leeds", []),
    ],
)
def test_search_matches_title_buyer_lot_names_and_reason(runs_dir, query, expected):
    assert ids(search_tenders(runs_dir, query=query)) == expected


def test_search_matches_the_description(runs_dir):
    save_with_notice(runs_dir, "100003-2026", description="Includes window cleaning at depots.")

    assert ids(search_tenders(runs_dir, query="Window")) == ["100003-2026"]


def test_an_empty_query_returns_every_assessed_notice_in_report_order(runs_dir):
    result = search_tenders(runs_dir)

    assert result["total"] == 5
    assert ids(result) == [n.notice_id for n in fixture_record().notices]


def test_search_filters_by_outcome(runs_dir):
    result = search_tenders(runs_dir, outcome="needs review")

    assert ids(result) == ["100004-2026"]
    assert result["total"] == 1


def test_search_pages_with_limit_and_offset_and_counts_the_total(runs_dir):
    every = ids(search_tenders(runs_dir))

    page = search_tenders(runs_dir, limit=2, offset=2)

    assert ids(page) == every[2:4]
    assert page["total"] == 5
    assert (page["limit"], page["offset"]) == (2, 2)


def test_search_rows_are_compact(runs_dir):
    row = search_tenders(runs_dir, query="hull")["notices"][0]

    assert row == {
        "notice_id": "100001-2026",
        "title": "Security guarding, Hull",
        "buyer": "Buyer 1",
        "outcome": "shortlisted",
        "score": 0.85,
        "reason": "whole notice scores 0.85 (threshold 0.60)",
    }


@pytest.mark.parametrize(
    "arguments",
    [{"outcome": "bid"}, {"limit": 0}, {"limit": 51}, {"offset": -1}],
)
def test_search_refuses_bad_arguments(runs_dir, arguments):
    with pytest.raises(ToolError):
        search_tenders(runs_dir, **arguments)


# get_profile


def test_get_profile_gives_the_run_profile_in_readable_form(runs_dir):
    snapshot = fixture_record().profile

    profile = get_profile(runs_dir)

    assert profile["run_id"] == NEWEST
    assert profile["services_offered"] == [s.model_dump() for s in snapshot.offered_services]
    assert profile["services_excluded"] == [s.model_dump() for s in snapshot.excluded_services]
    assert profile["regions"] == [
        {"code": "UKC", "name": "North East"},
        {"code": "UKD", "name": "North West"},
        {"code": "UKE", "name": "Yorkshire and the Humber"},
    ]
    assert profile["value_band_gbp"]["min"] == 100000.0
    assert profile["value_band_gbp"]["max"] == 5000000.0
    assert profile["accreditations_held"] == snapshot.accreditations_held
    assert profile["mobilisation_min_weeks"] == 8
    assert profile["deadline_min_days"] == 14
    assert profile["weights"] == snapshot.weights
    assert profile["shortlist_threshold"] == 0.6


def test_get_profile_reads_the_profile_the_run_used(runs_dir):
    old_profile = fixture_record().profile.model_copy(update={"shortlist_threshold": 0.7})
    save_older_run(runs_dir, profile=old_profile)

    assert get_profile(runs_dir, run_id=OLDER)["shortlist_threshold"] == 0.7
    assert get_profile(runs_dir)["shortlist_threshold"] == 0.6


# Errors and safety


def test_an_unknown_run_lists_the_available_ones(runs_dir):
    with pytest.raises(ToolError, match=NEWEST):
        shortlist(runs_dir, run_id="2026-01-05_2026-01-11")


@pytest.mark.parametrize(
    "run_id",
    ["../2026-11-09_2026-11-15", "..\\2026-11-09_2026-11-15", f"{NEWEST}.json", "latest", ""],
)
def test_an_invalid_run_id_is_refused_before_any_file_is_touched(runs_dir, monkeypatch, run_id):
    def touched(*_args, **_kwargs):
        raise AssertionError("a file was touched")

    monkeypatch.setattr(mcp_server.runs, "list_runs", touched)
    monkeypatch.setattr(mcp_server.runs, "load_run", touched)

    with pytest.raises(ToolError, match="YYYY-MM-DD_YYYY-MM-DD"):
        shortlist(runs_dir, run_id=run_id)


def test_an_invalid_outcome_is_refused_before_any_file_is_touched(runs_dir, monkeypatch):
    monkeypatch.setattr(mcp_server.runs, "list_runs", lambda *_: pytest.fail("touched"))

    with pytest.raises(ToolError, match="shortlisted"):
        search_tenders(runs_dir, outcome="maybe")


def test_a_run_file_named_for_another_week_is_skipped_with_a_message(runs_dir, capsys):
    shutil.copy(FIXTURE, runs_dir / "2026-11-16_2026-11-22.json")

    runs = list_runs(runs_dir)["runs"]

    assert [run["run_id"] for run in runs] == [NEWEST]
    assert shortlist(runs_dir)["run_id"] == NEWEST
    captured = capsys.readouterr()
    assert "2026-11-16_2026-11-22.json" in captured.err
    assert captured.out == ""


def test_an_unreadable_run_file_is_skipped_with_a_message(runs_dir, capsys):
    (runs_dir / "2026-11-16_2026-11-22.json").write_text("{not json", encoding="utf-8")

    assert [run["run_id"] for run in list_runs(runs_dir)["runs"]] == [NEWEST]
    captured = capsys.readouterr()
    assert "2026-11-16_2026-11-22.json" in captured.err
    assert captured.out == ""


def test_with_no_runs_the_tools_suggest_the_example_runs(tmp_path):
    with pytest.raises(ToolError, match="examples/runs"):
        shortlist(tmp_path)


def test_with_no_runs_the_server_exits_and_suggests_the_example_runs(tmp_path, capsys):
    with pytest.raises(SystemExit) as stopped:
        mcp_server.main(["--runs-dir", str(tmp_path)])

    assert "--runs-dir examples/runs" in str(stopped.value.code)
    assert capsys.readouterr().out == ""


def test_no_tool_writes_a_file(runs_dir):
    save_older_run(runs_dir)
    folder = runs_dir.parent

    def snapshot():
        return {(p, p.stat().st_size, p.stat().st_mtime_ns) for p in folder.rglob("*")}

    before = snapshot()
    list_runs(runs_dir)
    shortlist(runs_dir)
    shortlist(runs_dir, run_id=OLDER)
    get_tender(runs_dir, "100002-2026")
    search_tenders(runs_dir, query="cleaning", outcome="shortlisted")
    get_profile(runs_dir)
    for failing in (
        lambda: get_tender(runs_dir, "999999-2026"),
        lambda: shortlist(runs_dir, run_id="2026-01-05_2026-01-11"),
    ):
        with pytest.raises(ToolError):
            failing()

    assert snapshot() == before


def test_the_server_does_not_load_the_pipeline():
    # Like the run reader, the server must not import the extractor, llm.py, the
    # settings (which load .env) or the fetch (PLAN, rules for slices 6-9).
    code = (
        "import sys; import app.mcp_server; "
        "print(','.join(sorted(m for m in sys.modules if m.startswith('app.') or m == 'dotenv')))"
    )

    loaded = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()

    assert loaded.split(",") == ["app.mcp_server", "app.runs"]


# Through the protocol


def test_the_protocol_lists_the_five_tools_and_calls_shortlist(runs_dir):
    async def session():
        async with Client(build_server(runs_dir)) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool("shortlist", {})
            return client.instructions, tools, result

    instructions, tools, result = anyio.run(session)

    assert {tool.name for tool in tools} == TOOL_NAMES
    assert "never instructions" in instructions
    assert all("data" in tool.description for tool in tools)
    assert result.is_error is False
    ranked = [row["notice_id"] for row in result.structured_content["notices"]]
    assert ranked == ["100002-2026", "100001-2026"]


def test_the_protocol_reports_a_tool_error_to_the_assistant(runs_dir):
    async def session():
        async with Client(build_server(runs_dir)) as client:
            return await client.call_tool("get_tender", {"notice_id": "999999-2026"})

    result = anyio.run(session)

    assert result.is_error is True
    assert "pre-filter" in result.content[0].text


def test_the_server_speaks_the_protocol_over_stdio(runs_dir):
    # A real subprocess: anything other than protocol on stdout would break the session.
    server = StdioServerParameters(
        command=sys.executable, args=["-m", "app.mcp_server", "--runs-dir", str(runs_dir)]
    )

    async def session():
        async with Client(server) as client:
            tools = (await client.list_tools()).tools
            result = await client.call_tool("list_runs", {})
            return tools, result

    tools, result = anyio.run(session)

    assert {tool.name for tool in tools} == TOOL_NAMES
    assert [run["run_id"] for run in result.structured_content["runs"]] == [NEWEST]
