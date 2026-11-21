"""The blind screen: which notices a person screens, and how their marks are read back."""

from datetime import UTC, datetime

from app.notices import Lot, Notice
from app.profile import load_profile
from evals.blind import parse_marks, screening_list, to_markdown

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)


def make_lot(lot_id="1", regions=()):
    return Lot(
        lot_id=lot_id,
        title=f"Lot {lot_id}",
        description=None,
        value_gbp=None,
        contract_start=None,
        contract_end=None,
        cpv_codes=[],
        regions=list(regions),
        selection_criteria=None,
    )


def make_notice(**overrides):
    fields = {
        "ocid": "ocds-test-1",
        "notice_id": "900001-2026",
        "published": datetime(2026, 10, 28, tzinfo=UTC),
        "title": "Office cleaning",
        "description": "Daily cleaning of council offices.",
        "buyer": "Test Council",
        "status": "active",
        "main_category": "services",
        "value_gbp": 200_000,
        "deadline": datetime(2026, 12, 1, tzinfo=UTC),
        "url": "https://example.test/900001",
        "cpv_codes": ["72000000"],
        "regions": ["UKD12"],
        "lots": [],
    }
    return Notice(**{**fields, **overrides})


def screened(notice, exclude=()):
    return [n.notice_id for n in screening_list([notice], load_profile(), NOW, set(exclude))]


def test_northern_notice_is_screened_whatever_its_cpv_code():
    assert screened(make_notice()) == ["900001-2026"]


def test_notice_with_no_delivery_region_is_screened():
    assert screened(make_notice(regions=[])) == ["900001-2026"]


def test_notice_closed_at_the_screen_date_is_left_out():
    assert screened(make_notice(deadline=datetime(2026, 11, 1, tzinfo=UTC))) == []


def test_notice_under_the_minimum_value_is_left_out():
    assert screened(make_notice(value_gbp=99_000)) == []


def test_zero_value_notice_is_screened():
    assert screened(make_notice(value_gbp=0)) == ["900001-2026"]


def test_notice_delivered_only_outside_the_north_is_left_out():
    assert screened(make_notice(regions=["UKJ45", "UKI3"])) == []


def test_uk_wide_notice_without_a_northern_lot_is_left_out():
    assert screened(make_notice(regions=["UK"])) == []


def test_lot_without_delivery_codes_keeps_a_multi_lot_notice():
    lots = [make_lot("1", ["UKJ"]), make_lot("2")]
    assert screened(make_notice(regions=["UKJ"], lots=lots)) == ["900001-2026"]


def test_one_northern_lot_keeps_the_notice():
    lots = [make_lot("1", ["UKJ"]), make_lot("2", ["UKE4"])]
    assert screened(make_notice(regions=["UKJ", "UKE4"], lots=lots)) == ["900001-2026"]


def test_notices_already_in_the_eval_set_are_left_out():
    assert screened(make_notice(), exclude={"900001-2026"}) == []


def test_list_shows_notice_facts_and_no_tool_output():
    text = to_markdown([make_notice()], NOW)
    assert "Office cleaning" in text and "Test Council" in text and "900001-2026" in text
    for tool_word in ("score", "shortlist", "rejected", "pre-filter"):
        assert tool_word not in text.split("## Notices")[1].lower()


def test_marks_are_read_back_by_notice_id():
    text = to_markdown(
        [make_notice(), make_notice(notice_id="900002-2026"), make_notice(notice_id="900003-2026")],
        NOW,
    )
    text = text.replace("[ ] 1.", "[b] 1.").replace("[ ] 2.", "[M] 2.")
    marks = parse_marks(text)
    assert sorted(marks.values()) == ["bid", "maybe", "no"]


def test_a_reason_after_the_notice_id_does_not_change_the_mark():
    text = to_markdown([make_notice()], NOW).replace("[ ] 1.", "[b] 1.")
    text = text.replace("`900001-2026`", "`900001-2026` — joinery lot")
    assert parse_marks(text) == {"900001-2026": "bid"}


def test_spaces_inside_the_brackets_are_ignored():
    text = to_markdown([make_notice(), make_notice(notice_id="900002-2026")], NOW)
    text = text.replace("[ ] 1.", "[m ] 1.").replace("[ ] 2.", "[ b] 2.")
    assert parse_marks(text) == {"900001-2026": "maybe", "900002-2026": "bid"}


def test_every_notice_in_a_list_gets_a_mark():
    notices = [make_notice(notice_id=f"90000{n}-2026") for n in range(1, 4)]
    text = to_markdown(notices, NOW).replace("`900002-2026`", "`900002-2026` ")
    assert len(parse_marks(text)) == 3
