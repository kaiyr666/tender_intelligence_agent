"""The whole CLI run, end to end: fetch -> pre-filter -> extract -> score -> explain -> report.

Only the edges are faked: HTTP (at urllib's urlopen, so the real fetch code
runs), the clock, the LLM provider and the folders written to. Everything in
between is the real pipeline.
"""

import csv
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime

import pytest

import app.__main__ as cli
from app.fetch import API_URL, first_page_url

NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
DATE_FROM, DATE_TO = date(2026, 11, 9), date(2026, 11, 15)
PAGE_2 = API_URL + "?cursor=page-2"
CATERING_QUOTE = "Provision of school catering services across the borough"
RATIONALE = "Office cleaning in Yorkshire within the value band; mobilisation is not stated."


def release(number, title, description, cpv, value=300_000, tag="tender", region="UKE42"):
    return {
        "ocid": f"ocds-test-{number}",
        "id": f"20000{number}-2026",
        "date": "2026-11-12T10:00:00Z",
        "tag": [tag],
        "buyer": {"name": f"Test Council {number}"},
        "tender": {
            "title": title,
            "description": description,
            "status": "active",
            "value": {"amount": value, "currency": "GBP"},
            "tenderPeriod": {"endDate": "2026-12-18T12:00:00Z"},
            "classification": {"scheme": "CPV", "id": cpv},
            "items": [{"deliveryAddresses": [{"region": region}]}],
        },
    }


OFFICE = release(1, "Office cleaning, Leeds", "Daily office cleaning of civic offices.", "90910000")
CATERING = release(2, "School services", f"{CATERING_QUOTE}.", "90910000")
IT = release(3, "Network support", "IT network support.", "72000000")
PLANNING = release(4, "Future guarding", "Market engagement.", "79710000", tag="planning")


def extraction(primary, quote=None):
    return json.dumps(
        {
            "notice_mandatory_accreditations": [],
            "notice_preferred_accreditations": [],
            "red_flags": [],
            "lots": [
                {
                    "lot_id": "whole",
                    "services": [primary],
                    "primary_service": primary,
                    "primary_service_quote": quote,
                    "region_nuts1": ["UKE"],
                    "contract_length_months": 36,
                    "mobilisation_weeks": None,
                    "mandatory_accreditations": [],
                    "preferred_accreditations": [],
                }
            ],
        }
    )


OFFICE_EXTRACTION = extraction("office and commercial cleaning")
CATERING_EXTRACTION = extraction("catering", CATERING_QUOTE)


class FakeResponse:
    def __init__(self, body):
        self.status, self.headers, self._body = 200, {}, body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def page(releases, next_url=None):
    body = {"releases": releases, "links": {"next": next_url} if next_url else {}}
    return json.dumps(body).encode()


class FakeApi:
    """Two pages of releases; page 2 can be made to fail with HTTP 503."""

    def __init__(self, page_2_fails=False):
        self.page_2_fails = page_2_fails
        self.urls = []

    def urlopen(self, request, timeout):
        url = request.full_url
        self.urls.append(url)
        if url == first_page_url(DATE_FROM, DATE_TO):
            return FakeResponse(page([OFFICE, CATERING], PAGE_2))
        if url == PAGE_2 and not self.page_2_fails:
            return FakeResponse(page([IT, PLANNING]))
        if url == PAGE_2:
            raise urllib.error.HTTPError(url, 503, "busy", {"Retry-After": "0"}, io.BytesIO())
        raise AssertionError(f"unexpected URL {url}")


class FixedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW


@pytest.fixture
def cli_run(tmp_path, monkeypatch, fake_llm):
    """Returns run(api): main() with fakes at the edges, writing only under tmp_path."""
    for name, value in {
        "LLM_PROVIDER": "openai",
        "LLM_MODEL": fake_llm.model,
        "LLM_INPUT_USD_PER_MTOK": "1",
        "LLM_OUTPUT_USD_PER_MTOK": "10",
        "LLM_BUDGET_USD": "1",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(cli, "datetime", FixedClock)
    monkeypatch.setattr(cli, "get_provider", lambda: fake_llm)
    monkeypatch.setattr(cli, "DATA_DIR", tmp_path / "raw")
    monkeypatch.setattr(cli, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(cli, "OUTPUT_DIR", tmp_path / "output")
    argv = ["app", "--from", DATE_FROM.isoformat(), "--to", DATE_TO.isoformat()]
    monkeypatch.setattr(sys, "argv", argv)

    def run(api):
        monkeypatch.setattr(urllib.request, "urlopen", api.urlopen)
        cli.main()
        output = tmp_path / "output"
        report = (output / "report.md").read_text(encoding="utf-8")
        rows = list(csv.DictReader(io.StringIO((output / "shortlist.csv").read_text("utf-8-sig"))))
        return report, rows

    return run


def test_a_week_runs_from_fetch_to_report(cli_run, fake_llm, tmp_path):
    fake_llm.reply_with(
        OFFICE_EXTRACTION, CATERING_EXTRACTION, json.dumps({"rationale": RATIONALE})
    )

    report, rows = cli_run(FakeApi())

    assert "## Shortlisted (1)" in report
    assert "Office cleaning, Leeds" in report
    assert RATIONALE in report
    assert "## Rejected after extraction (1)" in report
    assert "main service is catering" in report
    assert "3 tender notices; 2 kept by the pre-filter" in report
    assert "1 planning-stage notices" in report
    assert "INCOMPLETE" not in report
    assert "Open Government Licence v3.0" in report
    assert [(r["notice_id"], r["outcome"]) for r in rows] == [
        ("200001-2026", "shortlisted"),
        ("200002-2026", "rejected"),
    ]
    assert len(fake_llm.calls) == 3  # two extractions and one rationale; IT never reaches the LLM
    assert (tmp_path / "raw" / "notices_2026-11-09_2026-11-15.json").exists()


def test_a_fetch_that_stops_partway_still_reports_with_a_banner(cli_run, fake_llm):
    fake_llm.reply_with(
        OFFICE_EXTRACTION, CATERING_EXTRACTION, json.dumps({"rationale": RATIONALE})
    )

    report, _ = cli_run(FakeApi(page_2_fails=True))

    assert "INCOMPLETE" in report
    assert "HTTP 503" in report
    assert "## Shortlisted (1)" in report


def test_a_rerun_uses_cached_extractions(cli_run, fake_llm):
    rationale = json.dumps({"rationale": RATIONALE})
    fake_llm.reply_with(OFFICE_EXTRACTION, CATERING_EXTRACTION, rationale, rationale)

    cli_run(FakeApi())
    report, _ = cli_run(FakeApi())

    assert len(fake_llm.calls) == 4  # the second run only writes the rationale again
    assert "## Shortlisted (1)" in report
