"""The eval harness: shortlist counts, lot checks, field matching and the offline run."""

from datetime import UTC, datetime

import pytest

from app.extract import WHOLE_NOTICE, Extraction, LotExtraction, RedFlag, Requirement
from app.llm import Usage
from app.notices import Lot, Notice
from app.profile import load_profile
from app.score import ELIGIBLE, GATED, LotResult, NoticeResult
from evals.run import (
    MODEL_FILE,
    CachedOnly,
    CaseRow,
    compare_fields,
    confusion,
    load_cases,
    load_notices,
    lot_check,
    run_eval,
    same_requirements,
    sweep,
)


def lot_x(lot_id="1", **overrides):
    fields = {
        "lot_id": lot_id,
        "services": ["office and commercial cleaning"],
        "primary_service": "office and commercial cleaning",
        "primary_service_quote": None,
        "region_nuts1": ["UKD"],
        "contract_length_months": 36,
        "mobilisation_weeks": None,
        "mandatory_accreditations": [],
        "preferred_accreditations": [],
    }
    return LotExtraction(**{**fields, **overrides})


def extraction(*lots, notice_required=(), red_flags=()):
    return Extraction(
        notice_mandatory_accreditations=list(notice_required),
        notice_preferred_accreditations=[],
        red_flags=list(red_flags),
        lots=list(lots) or [lot_x()],
    )


def expected(**overrides):
    fields = {
        "lot_id": "1",
        "primary_service": "office and commercial cleaning",
        "services": ["office and commercial cleaning"],
        "region_nuts1": ["UKD"],
        "contract_length_months": 36,
        "mobilisation_weeks": "not stated",
        "mandatory_accreditations": [],
        "tupe": "not stated",
    }
    return {**fields, **overrides}


def make_lot(lot_id, regions):
    return Lot(
        lot_id=lot_id,
        title=None,
        description=None,
        value_gbp=None,
        contract_start=None,
        contract_end=None,
        cpv_codes=[],
        regions=regions,
        selection_criteria=None,
    )


def lot_result(lot_id, status, score=0.9):
    return LotResult(lot_id, f"Lot {lot_id}", status, [], [], score)


def make_notice(**overrides):
    fields = {
        "ocid": "ocds-test-1",
        "notice_id": "900001-2026",
        "published": datetime(2026, 11, 13, tzinfo=UTC),
        "title": "Test",
        "description": None,
        "buyer": None,
        "status": "active",
        "main_category": "services",
        "value_gbp": None,
        "deadline": None,
        "url": "https://example.test",
        "cpv_codes": [],
        "regions": [],
        "lots": [],
    }
    return Notice(**{**fields, **overrides})


def notice_result(*lots, best=None, outcome="shortlisted"):
    return NoticeResult(make_notice(), outcome, "", best, list(lots), None)


def compare(labels, extracted, notice=None):
    """compare_fields for a notice without delivery addresses unless one is given."""
    return compare_fields(labels, extracted, notice or make_notice())


def row(bid, outcome, best_score=None):
    return CaseRow(
        case_id="x",
        case_set="tuning",
        bid=bid,
        outcome=outcome,
        reason="",
        best_score=best_score,
        best_lot=None,
        chosen_lot_ok=None,
        wrongly_gated_lots=[],
        field_hits={},
    )


# confusion: shortlisted is the positive prediction


def test_confusion_counts_each_cell():
    rows = [
        row(True, "shortlisted"),
        row(True, "shortlisted"),
        row(False, "shortlisted"),
        row(True, "rejected"),
        row(True, "dropped by pre-filter"),
        row(False, "rejected"),
    ]
    counts = confusion(rows)
    assert (counts["tp"], counts["fp"], counts["fn"], counts["tn"]) == (2, 1, 2, 1)


def test_confusion_precision_and_recall():
    rows = [row(True, "shortlisted"), row(False, "shortlisted"), row(True, "needs review")]
    counts = confusion(rows)
    assert (counts["precision"], counts["recall"]) == (0.5, 0.5)


def test_needs_review_bid_is_a_false_negative():
    assert confusion([row(True, "needs review")])["fn"] == 1


def test_precision_is_none_when_nothing_is_shortlisted():
    assert confusion([row(True, "rejected")])["precision"] is None


def test_recall_is_none_without_bid_cases():
    assert confusion([row(False, "rejected")])["recall"] is None


# sweep: re-deciding at other thresholds from the best eligible lot score


def test_sweep_shortlists_at_or_above_each_threshold():
    rows = [row(True, "shortlisted", 0.9), row(False, "shortlisted", 0.65), row(True, "x", None)]
    by_threshold = {t: (p, r) for t, p, r in sweep(rows, [0.6, 0.7])}
    assert by_threshold[0.6] == (0.5, 0.5)
    assert by_threshold[0.7] == (1.0, 0.5)


# lot_check: the chosen lot must be one the team would bid


def test_chosen_lot_in_bid_lots_is_ok():
    best = lot_result("3", ELIGIBLE)
    ok, _ = lot_check(["2", "3"], notice_result(best, best=best))
    assert ok is True


def test_chosen_lot_outside_bid_lots_is_not_ok():
    best = lot_result("1", ELIGIBLE)
    ok, _ = lot_check(["2", "3"], notice_result(best, lot_result("3", ELIGIBLE), best=best))
    assert ok is False


def test_lot_check_is_none_when_no_lot_was_chosen():
    ok, _ = lot_check(["1"], notice_result(lot_result("1", GATED), outcome="rejected"))
    assert ok is None


def test_lot_check_is_none_for_a_no_bid_case():
    best = lot_result("1", ELIGIBLE)
    ok, _ = lot_check([], notice_result(best, best=best))
    assert ok is None


def test_bid_lots_that_were_gated_are_listed():
    result = notice_result(
        lot_result("3a", GATED), lot_result("3b", GATED), lot_result("4", ELIGIBLE)
    )
    _, wrongly_gated = lot_check(["3a", "4"], result)
    assert wrongly_gated == ["3a"]


def test_lot_check_without_a_result():
    assert lot_check(["1"], None) == (None, [])


# same_requirements: names compared loosely, "one of" groups as sets of schemes


def test_requirements_match_ignoring_case_and_punctuation():
    assert same_requirements(["Cyber Essentials Plus"], ["cyber-essentials plus"])


def test_one_of_group_matches_in_any_order_and_wording():
    expected_group = ["one of: Constructionline, CHAS, SafeContractor or SSIP"]
    actual = ["One of: CHAS, SafeContractor, Constructionline or SSIP"]
    assert same_requirements(expected_group, actual)


def test_one_of_group_with_a_different_scheme_does_not_match():
    assert not same_requirements(["one of: CHAS or SafeContractor"], ["one of: CHAS or SMAS"])


def test_missing_requirement_does_not_match():
    assert not same_requirements(["BAFE registration"], [])


def test_no_requirements_on_either_side_match():
    assert same_requirements([], [])


# compare_fields: one hit or miss per expected field of the expected lot


def test_all_fields_match_a_faithful_extraction():
    hits = compare(expected(), extraction())
    assert hits and all(hits.values())


def test_services_are_compared_as_a_set():
    lot = lot_x(services=["grounds maintenance", "office and commercial cleaning"])
    labels = expected(services=["office and commercial cleaning", "grounds maintenance"])
    assert compare(labels, extraction(lot))["services"] is True


def test_expected_other_matches_any_other_service():
    lot = lot_x(primary_service="other: pest control")
    assert compare(expected(primary_service="other"), extraction(lot))["primary_service"]


def test_expected_other_does_not_match_an_offered_label():
    hits = compare(expected(primary_service="other"), extraction())
    assert hits["primary_service"] is False


def test_not_stated_matches_null_and_empty():
    lot = lot_x(region_nuts1=[], contract_length_months=None)
    labels = expected(region_nuts1="not stated", contract_length_months="not stated")
    hits = compare(labels, extraction(lot))
    assert hits["region_nuts1"] and hits["contract_length_months"]


def test_not_stated_does_not_match_a_value():
    hits = compare(expected(contract_length_months="not stated"), extraction())
    assert hits["contract_length_months"] is False


def test_region_must_match_exactly():
    lot = lot_x(region_nuts1=["UKD", "UKE"])
    assert compare(expected(), extraction(lot))["region_nuts1"] is False


def test_mobilisation_compares_numbers():
    lot = lot_x(mobilisation_weeks=6.0)
    assert compare(expected(mobilisation_weeks=6), extraction(lot))["mobilisation_weeks"]


def test_notice_wide_requirements_count_for_the_lot():
    required = Requirement(name="BAFE registration", quote="must be BAFE registered")
    labels = expected(mandatory_accreditations=["BAFE registration"])
    hits = compare(labels, extraction(notice_required=[required]))
    assert hits["mandatory_accreditations"] is True


def test_tupe_flag_matches_expected_yes():
    flag = RedFlag(kind="tupe", quote="TUPE will apply to this contract")
    hits = compare(expected(tupe="yes"), extraction(red_flags=[flag]))
    assert hits["tupe"] is True


def test_tupe_not_stated_fails_when_flagged():
    flag = RedFlag(kind="tupe", quote="TUPE will apply to this contract")
    assert compare(expected(), extraction(red_flags=[flag]))["tupe"] is False


def test_expected_lot_missing_from_extraction_gives_no_comparison():
    assert compare(expected(lot_id="2"), extraction()) == {}


def test_no_extraction_gives_no_comparison():
    assert compare(expected(), None) == {}


def test_notice_without_lots_compares_the_whole_notice_lot():
    hits = compare(expected(lot_id=None), extraction(lot_x(lot_id=WHOLE_NOTICE)))
    assert hits and all(hits.values())


def test_region_from_delivery_addresses_wins_over_the_text():
    notice = make_notice(regions=["UKF2"])
    hits = compare(expected(region_nuts1=["UKF"]), extraction(lot_x(region_nuts1=[])), notice)
    assert hits["region_nuts1"] is True


def test_delivery_codes_are_compared_at_nuts_1():
    notice = make_notice(regions=["UKD42", "UKD1"])
    assert compare(expected(region_nuts1=["UKD"]), extraction(), notice)["region_nuts1"] is True


def test_lot_delivery_codes_are_used_for_that_lot():
    lots = [make_lot("1", ["UKC14"]), make_lot("2", ["UKJ"])]
    notice = make_notice(lots=lots)
    x = extraction(lot_x("1", region_nuts1=[]), lot_x("2", region_nuts1=[]))
    assert compare(expected(region_nuts1=["UKC"]), x, notice)["region_nuts1"] is True


def test_uk_wide_delivery_code_stays_uk():
    notice = make_notice(regions=["UK"])
    assert compare(expected(region_nuts1=["UK"]), extraction(), notice)["region_nuts1"] is True


def test_requirement_filler_words_and_iso_years_are_ignored():
    labels = ["one of: Constructionline, CHAS, SafeContractor or SSIP"]
    assert same_requirements(
        labels, ["one of: Constructionline, CHAS, SafeContractor or SSIP accreditation"]
    )
    assert same_requirements(["ISO 9001:2015"], ["ISO 9001"])


def test_unknown_expected_field_is_an_error():
    with pytest.raises(KeyError):
        compare(expected(colour="blue"), extraction())


# The eval from a clean clone: committed notices and extractions, no API key, no LLM call


def test_eval_runs_offline_on_committed_extractions():
    cases = load_cases()
    provider = CachedOnly(MODEL_FILE.read_text(encoding="utf-8").strip())
    usage = Usage()
    rows = run_eval(cases, load_notices(), load_profile(), provider, usage)
    assert [r.case_id for r in rows] == [c["notice_id"] for c in cases]
    assert usage.calls == 0


def test_every_case_has_a_notice_and_a_known_set():
    notice_ids = {n.notice_id for n in load_notices()}
    for case in load_cases():
        assert case["notice_id"] in notice_ids
        assert case["set"] in ("tuning", "check")
