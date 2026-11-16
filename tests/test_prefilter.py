"""Code pre-filter: CPV matching against the profile and the drop reasons."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.notices import Lot, Notice, build_notices
from app.prefilter import CLOSED, LOW_VALUE, NO_CPV_MATCH, cpv_matches, prefilter
from app.profile import CpvRules, load_profile

UTC = UTC
NOW = datetime(2026, 11, 16, tzinfo=UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "releases_sample.json"


@pytest.fixture(scope="module")
def profile():
    return load_profile()


def make_lot(**overrides):
    fields = {
        "lot_id": "1",
        "title": None,
        "description": None,
        "value_gbp": None,
        "contract_start": None,
        "contract_end": None,
        "cpv_codes": [],
        "regions": [],
        "selection_criteria": None,
    }
    return Lot(**{**fields, **overrides})


def make_notice(**overrides):
    """A notice that passes every check unless a test overrides a field."""
    fields = {
        "ocid": "ocds-test-1",
        "notice_id": "900001-2026",
        "published": datetime(2026, 11, 13, tzinfo=UTC),
        "title": "Office cleaning",
        "description": None,
        "buyer": "Test Council",
        "status": "active",
        "main_category": "services",
        "value_gbp": 200_000,
        "deadline": datetime(2026, 12, 1, 12, 0, tzinfo=UTC),
        "url": "https://www.find-tender.service.gov.uk/Notice/900001-2026",
        "cpv_codes": ["90910000"],
        "regions": [],
        "lots": [],
    }
    return Notice(**{**fields, **overrides})


def reason_for(notice, profile):
    [screened] = prefilter([notice], profile, NOW)
    return screened.drop_reason


# cpv_matches with the real profile


@pytest.mark.parametrize(
    "code",
    [
        "90910000",  # a profile code itself
        "90911200",  # under 90910000
        "90919200",  # under 90910000
        "50711000",  # under 50700000
        "45453100",  # under 45453000
        "98341130",  # an exact, fully specific profile code
        "50000000",  # broad code, exact
        "90900000",  # broad code, exact
    ],
)
def test_cpv_code_matches_profile(code, profile):
    assert cpv_matches(code, profile.cpv) is True


@pytest.mark.parametrize(
    "code",
    [
        "55100000",  # different division from 50700000
        "50100000",  # under broad 50000000, which matches only exactly
        "90920000",  # under broad 90900000 but not under 90910000
        "72000000",  # unrelated (IT services)
    ],
)
def test_cpv_code_does_not_match_profile(code, profile):
    assert cpv_matches(code, profile.cpv) is False


def test_profile_code_does_not_match_a_code_from_another_division():
    rules = CpvRules(codes=["50700000"], broad_codes=[])
    assert cpv_matches("55100000", rules) is False
    assert cpv_matches("50711000", rules) is True


def test_broad_code_matches_only_itself():
    rules = CpvRules(codes=[], broad_codes=["50000000"])
    assert cpv_matches("50000000", rules) is True
    assert cpv_matches("50100000", rules) is False


# prefilter: kept


def test_matching_open_notice_in_value_band_is_kept(profile):
    assert reason_for(make_notice(), profile) is None


def test_unknown_value_is_kept(profile):
    assert reason_for(make_notice(value_gbp=None), profile) is None


def test_unknown_deadline_is_kept(profile):
    assert reason_for(make_notice(deadline=None), profile) is None


def test_value_exactly_at_minimum_is_kept(profile):
    assert reason_for(make_notice(value_gbp=100_000), profile) is None


def test_value_over_maximum_is_not_dropped(profile):
    assert reason_for(make_notice(value_gbp=6_000_000), profile) is None


def test_cpv_only_on_a_lot_is_kept(profile):
    notice = make_notice(cpv_codes=[], lots=[make_lot(cpv_codes=["90911200"])])
    assert reason_for(notice, profile) is None


def test_any_matching_code_keeps_the_notice(profile):
    notice = make_notice(
        cpv_codes=["72000000"],
        lots=[
            make_lot(lot_id="1", cpv_codes=["72000000"]),
            make_lot(lot_id="2", cpv_codes=["50711000"]),
        ],
    )
    assert reason_for(notice, profile) is None


def test_notice_with_no_cpv_codes_at_all_is_kept(profile):
    notice = make_notice(cpv_codes=[], lots=[make_lot(cpv_codes=[])])
    assert reason_for(notice, profile) is None


# prefilter: dropped


def test_passed_deadline_is_closed(profile):
    notice = make_notice(deadline=datetime(2026, 11, 15, 12, 0, tzinfo=UTC))
    assert reason_for(notice, profile) == CLOSED


def test_complete_status_is_closed_even_with_future_deadline(profile):
    assert reason_for(make_notice(status="complete"), profile) == CLOSED


def test_value_under_minimum_is_dropped(profile):
    assert reason_for(make_notice(value_gbp=99_000), profile) == LOW_VALUE


def test_no_matching_cpv_code_is_dropped(profile):
    notice = make_notice(cpv_codes=["72000000"], lots=[make_lot(cpv_codes=["72200000"])])
    assert reason_for(notice, profile) == NO_CPV_MATCH


def test_closed_is_reported_before_low_value_and_cpv(profile):
    notice = make_notice(
        deadline=datetime(2026, 11, 1, tzinfo=UTC), value_gbp=50_000, cpv_codes=["72000000"]
    )
    assert reason_for(notice, profile) == CLOSED


def test_low_value_is_reported_before_cpv(profile):
    notice = make_notice(value_gbp=50_000, cpv_codes=["72000000"])
    assert reason_for(notice, profile) == LOW_VALUE


# prefilter: shape of the result


def test_every_notice_is_returned_in_order(profile):
    notices = [
        make_notice(notice_id="1-2026"),
        make_notice(notice_id="2-2026", value_gbp=10),
        make_notice(notice_id="3-2026"),
    ]
    screened = prefilter(notices, profile, NOW)
    assert [s.notice for s in screened] == notices


def test_empty_input_gives_empty_result(profile):
    assert prefilter([], profile, NOW) == []


# prefilter on the real fixture


def test_fixture_notices_get_expected_reasons(profile):
    releases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    screened = prefilter(build_notices(releases).tenders, profile, NOW)
    reasons = {s.notice.notice_id: s.drop_reason for s in screened}
    assert reasons == {
        "108109-2026": None,  # 90900000 broad, exact
        "108059-2026": None,  # 90910000 family
        "108091-2026": LOW_VALUE,  # £99,000
        "108230-2026": NO_CPV_MATCH,  # 50413100, 51700000
        "106268-2026": NO_CPV_MATCH,  # 45443000 facade work
    }
