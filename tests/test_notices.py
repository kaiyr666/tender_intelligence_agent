"""Raw OCDS releases become one reduced, contact-free Notice per tender.

Most expectations come from tests/fixtures/releases_sample.json (10 sanitised
real releases); small synthetic releases cover cases the fixture lacks.
"""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.notices import NOTICE_URL, Lot, Notice, build_notices, to_notice
from app.sanitise import EMAIL_PLACEHOLDER, PHONE_PLACEHOLDER

FIXTURE = Path(__file__).parent / "fixtures" / "releases_sample.json"
UTC = UTC


@pytest.fixture(scope="module")
def releases():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def batch(releases):
    return build_notices(releases)


@pytest.fixture(scope="module")
def by_id(batch):
    return {notice.notice_id: notice for notice in batch.tenders}


def synthetic(
    notice_id="900001-2026",
    ocid="ocds-test-1",
    released="2026-11-10T09:00:00Z",
    tag=("tender",),
    **tender_fields,
):
    """A minimal tender-stage release with only the fields a Notice needs."""
    tender = {"id": "T-1", "title": "Office cleaning", "status": "active", **tender_fields}
    return {
        "ocid": ocid,
        "id": notice_id,
        "date": released,
        "tag": list(tag),
        "buyer": {"id": "B-1", "name": "Test Council"},
        "tender": tender,
    }


# build_notices on the fixture


def test_fixture_gives_five_tenders(by_id):
    assert set(by_id) == {
        "108109-2026",
        "108230-2026",
        "106268-2026",
        "108059-2026",
        "108091-2026",
    }


def test_fixture_counts_two_planning_notices(batch):
    assert batch.planning_count == 2


def test_fixture_counts_one_cancelled_notice_as_withdrawn(batch):
    assert batch.withdrawn_count == 1


def test_two_releases_of_one_notice_give_one_notice_from_the_latest(batch, by_id):
    fire = [n for n in batch.tenders if n.ocid == "ocds-h6vhtk-07bc2c"]
    assert [n.notice_id for n in fire] == ["108230-2026"]
    assert by_id["108230-2026"].deadline == datetime(2026, 12, 14, 12, 0, tzinfo=UTC)


def test_award_release_is_not_a_tender(batch):
    assert "ocds-h6vhtk-07bc37" not in {n.ocid for n in batch.tenders}


def test_release_tagged_planning_and_tender_is_a_tender(by_id):
    assert by_id["106268-2026"].title == "CP-401 - Aster Group External Decorations"


# Notice fields on the fixture


def test_notice_keeps_title_buyer_and_published(by_id):
    notice = by_id["108109-2026"]
    assert notice.title == "009689 - Window and High Level Cleaning"
    assert notice.buyer == "Newcastle City Council"
    assert notice.published == datetime(2026, 11, 13, 15, 17, 29, tzinfo=UTC)


def test_notice_url_is_the_find_a_tender_notice_page(by_id):
    assert by_id["108109-2026"].url == "https://www.find-tender.service.gov.uk/Notice/108109-2026"


def test_notice_value_uses_net_amount(by_id):
    assert by_id["108109-2026"].value_gbp == 140000


def test_notice_value_falls_back_to_gross_amount_when_net_is_missing(by_id):
    assert by_id["108059-2026"].value_gbp == 1850000


def test_notice_deadline_is_the_tender_period_end(by_id):
    assert by_id["108109-2026"].deadline == datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def test_date_only_deadline_means_the_end_of_that_day(by_id):
    deadline = by_id["106268-2026"].deadline
    assert deadline.tzinfo is not None
    assert deadline.date() == date(2026, 11, 23)
    assert (deadline.hour, deadline.minute) == (23, 59)


def test_notice_cpv_codes_include_item_classifications(by_id):
    assert set(by_id["108059-2026"].cpv_codes) == {
        "90910000",
        "90911000",
        "90911100",
        "90911200",
        "90911300",
    }


def test_notice_cpv_codes_include_the_tender_classification(by_id):
    assert set(by_id["106268-2026"].cpv_codes) == {"45443000"}


def test_notice_regions_come_from_item_delivery_addresses(by_id):
    assert set(by_id["106268-2026"].regions) == {"UKJ", "UKI", "UKK"}


def test_notice_keeps_every_lot(by_id):
    lots = by_id["108109-2026"].lots
    assert [lot.title for lot in lots] == [
        "Public Buildings",
        "Residential Properties",
        "Tree Top Village",
    ]


def test_lot_gets_regions_of_its_own_items_only(by_id):
    regions = {lot.lot_id: lot.regions for lot in by_id["106268-2026"].lots}
    assert regions == {"1": ["UKJ"], "2": ["UKI"], "3": ["UKK"]}


def test_lot_gets_cpv_codes_of_its_items(by_id):
    lot = by_id["108230-2026"].lots[0]
    assert set(lot.cpv_codes) == {"50413100", "51700000"}


def test_lot_keeps_value_and_contract_dates(by_id):
    lot = by_id["108109-2026"].lots[0]
    assert lot.value_gbp == 140000
    assert (lot.contract_start, lot.contract_end) == (date(2027, 1, 1), date(2028, 12, 31))


def test_lot_without_value_or_dates_has_none(by_id):
    lot = by_id["106268-2026"].lots[0]
    assert (lot.value_gbp, lot.contract_start, lot.contract_end) == (None, None, None)


def test_lot_keeps_selection_criteria_text(by_id):
    criteria = by_id["108230-2026"].lots[0].selection_criteria
    assert "technical competence" in criteria


# Privacy


def test_contact_details_in_description_are_masked(by_id):
    description = by_id["108059-2026"].description
    assert "jane.example@example.org" not in description
    assert "0113 496 0002" not in description
    assert EMAIL_PLACEHOLDER in description and PHONE_PLACEHOLDER in description


def test_money_in_description_survives_masking(by_id):
    assert "£1,850,000" in by_id["108059-2026"].description


@pytest.mark.parametrize("forbidden", ["Jane Example", "example.org", "0113 496 000"])
def test_no_notice_contains_contact_details(batch, forbidden):
    for notice in batch.tenders:
        assert forbidden not in notice.model_dump_json(), notice.notice_id


def test_party_addresses_are_not_kept():
    release = synthetic(description="Office cleaning at the town hall.")
    release["parties"] = [
        {
            "name": "Test Council",
            "roles": ["buyer"],
            "address": {
                "streetAddress": "1 Example Street",
                "locality": "Exampleton",
                "postalCode": "ZZ1 1ZZ",
            },
            "contactPoint": {"name": "Jane Example", "email": "bids@example.org"},
        }
    ]
    dumped = to_notice(release).model_dump_json()
    for forbidden in ["1 Example Street", "Exampleton", "ZZ1 1ZZ", "Jane Example"]:
        assert forbidden not in dumped


# Synthetic edge cases


def test_withdrawn_status_counts_as_withdrawn():
    result = build_notices([synthetic(tag=("tenderUpdate",), status="withdrawn")])
    assert (result.tenders, result.withdrawn_count) == ([], 1)


def test_tender_cancelled_by_a_later_release_is_withdrawn():
    original = synthetic(notice_id="900001-2026", released="2026-11-10T09:00:00Z")
    cancelled = synthetic(
        notice_id="900002-2026",
        released="2026-11-12T09:00:00Z",
        tag=("tenderCancellation",),
        status="cancelled",
    )
    result = build_notices([original, cancelled])
    assert (result.tenders, result.withdrawn_count) == ([], 1)


def test_latest_release_by_date_wins_even_if_listed_first():
    later = synthetic(notice_id="900002-2026", released="2026-11-12T09:00:00Z", title="Updated")
    earlier = synthetic(notice_id="900001-2026", released="2026-11-10T09:00:00Z", title="Original")
    result = build_notices([later, earlier])
    assert [n.notice_id for n in result.tenders] == ["900002-2026"]


def test_different_ocids_give_separate_notices():
    result = build_notices([synthetic(ocid="ocds-a"), synthetic(ocid="ocds-b")])
    assert len(result.tenders) == 2


def test_empty_release_list_gives_empty_batch():
    result = build_notices([])
    assert (result.tenders, result.planning_count, result.withdrawn_count) == ([], 0, 0)


def test_url_falls_back_to_notice_url_without_a_tender_notice_document():
    notice = to_notice(synthetic(notice_id="900001-2026"))
    assert notice.url == NOTICE_URL.format(notice_id="900001-2026")


def test_missing_value_and_deadline_are_none():
    notice = to_notice(synthetic())
    assert (notice.value_gbp, notice.deadline) == (None, None)


def test_zero_value_is_not_stated():
    notice = to_notice(synthetic(value={"amount": 0, "currency": "GBP"}))
    assert notice.value_gbp is None


def test_zero_value_in_a_saved_notice_is_not_stated():
    saved = {**to_notice(synthetic()).model_dump(), "value_gbp": 0}
    assert Notice.model_validate(saved).value_gbp is None


def test_zero_lot_value_is_not_stated():
    lot = Lot(
        lot_id="1",
        title=None,
        description=None,
        value_gbp=0,
        contract_start=None,
        contract_end=None,
        cpv_codes=[],
        regions=[],
        selection_criteria=None,
    )
    assert lot.value_gbp is None


def test_gross_value_is_used_when_net_amount_is_absent():
    notice = to_notice(synthetic(value={"amountGross": 120000, "currency": "GBP"}))
    assert notice.value_gbp == 120000


def test_expression_of_interest_deadline_is_used_when_there_is_no_tender_period():
    notice = to_notice(synthetic(expressionOfInterestDeadline="2026-12-15T12:00:00+00:00"))
    assert notice.deadline == datetime(2026, 12, 15, 12, 0, tzinfo=UTC)


def test_tender_period_end_wins_over_expression_of_interest_deadline():
    notice = to_notice(
        synthetic(
            tenderPeriod={"endDate": "2026-12-20T12:00:00Z"},
            expressionOfInterestDeadline="2026-12-01T12:00:00Z",
        )
    )
    assert notice.deadline == datetime(2026, 12, 20, 12, 0, tzinfo=UTC)


def test_fixture_notice_without_tender_period_uses_its_expression_of_interest_deadline(by_id):
    assert by_id["108059-2026"].deadline == datetime(2026, 12, 15, 12, 0, tzinfo=UTC)
