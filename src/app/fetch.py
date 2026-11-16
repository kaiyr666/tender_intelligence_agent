"""Fetch OCDS releases from the Find a Tender API for a date range.

All stages are fetched and filtered in code: in testing, the API's `stages`
filter returned 41 tender releases for a week that had over 500.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date

API_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"
USER_AGENT = "tender-intelligence-poc/0.1"
PAGE_LIMIT = 100
MAX_ATTEMPTS = 5
RETRY_STATUSES = {429, 503}
DEFAULT_WAIT_SECONDS = 10.0
MAX_WAIT_SECONDS = 120.0


class FetchError(RuntimeError):
    """The API refused the request in a way retrying will not fix."""


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class FetchResult:
    releases: list[dict]
    complete: bool
    problem: str | None  # why the fetch stopped early, if it did


def first_page_url(date_from: date, date_to: date) -> str:
    """URL for releases updated from 00:00:00 on date_from to 23:59:59 on date_to."""
    query = urllib.parse.urlencode(
        {
            "updatedFrom": f"{date_from.isoformat()}T00:00:00",
            "updatedTo": f"{date_to.isoformat()}T23:59:59",
            "limit": PAGE_LIMIT,
        }
    )
    return f"{API_URL}?{query}"


def http_get(url: str, timeout: float = 60) -> HttpResponse:
    """One GET request. HTTP error statuses are returned, network failures raise OSError."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResponse(response.status, dict(response.headers), response.read())
    except urllib.error.HTTPError as error:
        return HttpResponse(error.code, dict(error.headers), error.read())


def fetch_releases(
    date_from: date,
    date_to: date,
    get: Callable[[str], HttpResponse] = http_get,
    sleep: Callable[[float], None] = time.sleep,
) -> FetchResult:
    """Follow `links.next` until the last page.

    429/503 wait for Retry-After and retry; network errors retry with backoff.
    After MAX_ATTEMPTS on one page the releases so far are returned with
    complete=False. Other HTTP errors raise FetchError.
    """
    releases: list[dict] = []
    url: str | None = first_page_url(date_from, date_to)
    seen_urls: set[str] = set()
    while url:
        if url in seen_urls:
            return FetchResult(releases, False, f"the API repeated a page link: {url}")
        seen_urls.add(url)
        page, problem = _get_page(url, get, sleep)
        if page is None:
            return FetchResult(releases, False, problem)
        releases.extend(page.get("releases") or [])
        url = (page.get("links") or {}).get("next")
    return FetchResult(releases, True, None)


def _get_page(
    url: str, get: Callable[[str], HttpResponse], sleep: Callable[[float], None]
) -> tuple[dict | None, str | None]:
    """One page as parsed JSON, or (None, reason) once every attempt has failed."""
    problem = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = get(url)
        except OSError as error:  # network failure or timeout: worth retrying
            problem = f"network error: {error}"
            sleep(min(2**attempt, MAX_WAIT_SECONDS))
            continue
        if response.status == 200:
            try:
                return json.loads(response.body), None
            except json.JSONDecodeError as error:
                raise FetchError(f"the API returned invalid JSON for {url}: {error}") from error
        if response.status in RETRY_STATUSES:
            problem = f"HTTP {response.status} after {MAX_ATTEMPTS} attempts"
            sleep(_retry_after(response.headers))
            continue
        raise FetchError(f"the API refused {url} with HTTP {response.status}")
    return None, f"stopped at {url}: {problem}"


def _retry_after(headers: Mapping[str, str]) -> float:
    """Seconds to wait from a Retry-After header (seconds form), capped."""
    value = next((v for k, v in headers.items() if k.lower() == "retry-after"), "")
    try:
        return min(max(float(value), 0), MAX_WAIT_SECONDS)
    except ValueError:
        return DEFAULT_WAIT_SECONDS
