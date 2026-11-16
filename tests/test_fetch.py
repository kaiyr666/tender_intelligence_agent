"""Fetching releases: the query URL, paging, retries and a fetch that stops partway.

A fake `get` stands in for HTTP and `sleep` only records waits, so nothing
touches the network or really sleeps.
"""

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest

from app.fetch import (
    API_URL,
    MAX_ATTEMPTS,
    FetchError,
    HttpResponse,
    fetch_releases,
    first_page_url,
)

DATE_FROM = date(2026, 11, 9)
DATE_TO = date(2026, 11, 15)
NEXT_URL = API_URL + "?cursor=page-2"


def page(releases, next_url=None):
    body = {"releases": releases}
    if next_url:
        body["links"] = {"next": next_url}
    return HttpResponse(200, {"Content-Type": "application/json"}, json.dumps(body).encode())


def error(status, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after else {}
    return HttpResponse(status, headers, b"")


class FakeApi:
    """Answers each URL with its queued outcomes; the last outcome repeats forever."""

    def __init__(self, outcomes_by_url):
        self.outcomes_by_url = {url: list(outcomes) for url, outcomes in outcomes_by_url.items()}
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        outcomes = self.outcomes_by_url[url]
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def run(outcomes_by_url):
    api = FakeApi(outcomes_by_url)
    sleeps = []
    result = fetch_releases(DATE_FROM, DATE_TO, get=api.get, sleep=sleeps.append)
    return result, api, sleeps


def first_url():
    return first_page_url(DATE_FROM, DATE_TO)


# first_page_url


def query_of(url):
    return parse_qs(urlsplit(url).query)


def test_first_page_url_points_at_the_api():
    parts = urlsplit(first_url())
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == API_URL


def test_first_page_url_covers_both_dates_inclusively():
    query = query_of(first_url())
    assert query["updatedFrom"] == ["2026-11-09T00:00:00"]
    assert query["updatedTo"] == ["2026-11-15T23:59:59"]


def test_first_page_url_for_a_single_day_spans_the_whole_day():
    query = query_of(first_page_url(date(2026, 11, 9), date(2026, 11, 9)))
    assert (query["updatedFrom"], query["updatedTo"]) == (
        ["2026-11-09T00:00:00"],
        ["2026-11-09T23:59:59"],
    )


def test_first_page_url_asks_for_100_per_page():
    assert query_of(first_url())["limit"] == ["100"]


def test_first_page_url_does_not_filter_by_stage():
    assert "stages" not in query_of(first_url())


# fetch_releases: paging


def test_two_pages_are_followed_and_releases_kept_in_order():
    result, _, _ = run(
        {
            first_url(): [page([{"id": "a"}, {"id": "b"}], next_url=NEXT_URL)],
            NEXT_URL: [page([{"id": "c"}])],
        }
    )
    assert result.releases == [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    assert (result.complete, result.problem) == (True, None)


def test_single_empty_page_is_a_complete_fetch_with_no_releases():
    result, _, _ = run({first_url(): [page([])]})
    assert (result.releases, result.complete) == ([], True)


# fetch_releases: retries


def test_429_waits_for_retry_after_then_retries():
    result, _, sleeps = run({first_url(): [error(429, retry_after="7"), page([{"id": "a"}])]})
    assert sleeps == [7]
    assert (result.releases, result.complete) == ([{"id": "a"}], True)


def test_503_is_retried():
    result, _, _ = run({first_url(): [error(503, retry_after="3"), page([{"id": "a"}])]})
    assert (result.releases, result.complete) == ([{"id": "a"}], True)


@pytest.mark.parametrize("failure", [OSError("connection reset"), TimeoutError("timed out")])
def test_network_failure_is_retried_after_a_wait(failure):
    result, _, sleeps = run({first_url(): [failure, page([{"id": "a"}])]})
    assert (result.releases, result.complete) == ([{"id": "a"}], True)
    assert len(sleeps) >= 1


# fetch_releases: giving up


def test_page_that_keeps_failing_returns_earlier_releases_marked_incomplete():
    result, api, _ = run(
        {
            first_url(): [page([{"id": "a"}], next_url=NEXT_URL)],
            NEXT_URL: [error(503, retry_after="1")],
        }
    )
    assert result.releases == [{"id": "a"}]
    assert result.complete is False
    assert result.problem
    assert api.calls.count(NEXT_URL) == MAX_ATTEMPTS


def test_network_down_from_the_start_gives_an_empty_incomplete_result():
    result, _, _ = run({first_url(): [OSError("no route to host")]})
    assert (result.releases, result.complete) == ([], False)
    assert result.problem


def test_400_raises_fetch_error_without_retrying():
    api = FakeApi({first_url(): [HttpResponse(400, {}, b"bad request")]})
    with pytest.raises(FetchError):
        fetch_releases(DATE_FROM, DATE_TO, get=api.get, sleep=lambda seconds: None)
    assert len(api.calls) == 1
