"""The saved run record: what the web view and the MCP server read instead of the pipeline."""

import csv
import io
import json
import os
from pathlib import Path

import pytest
from test_report import RATIONALES, RUN, scored_results

from app.profile import load_profile
from app.report import render_csv
from app.runs import (
    RUN_SCHEMA_VERSION,
    RunFileError,
    is_run_id,
    list_runs,
    load_run,
    save_run,
    to_record,
)
from app.score import SHORTLISTED

FIXTURE = Path(__file__).parent / "fixtures" / "runs" / "2026-11-09_2026-11-15.json"
EXAMPLE = Path(__file__).parents[1] / "examples" / "runs" / "2026-11-09_2026-11-15.json"
MODEL = "test-model"


def profile_with(**scoring_updates):
    profile = load_profile()
    scoring = profile.scoring.model_copy(update=scoring_updates)
    return profile.model_copy(update={"scoring": scoring})


# The same threshold as the report's fixed input, so reasons and snapshot agree.
PROFILE = profile_with(shortlist_threshold=RUN.threshold)


def record(results=None, rationales=RATIONALES, profile=PROFILE):
    return to_record(results or scored_results(), rationales, RUN, profile, MODEL)


def test_run_record_matches_the_fixture(tmp_path):
    # Slices 7 and 8 test against this file; regenerate it with UPDATE_GOLDEN=1.
    if os.environ.get("UPDATE_GOLDEN"):
        save_run(record(), FIXTURE.parent)

    path = save_run(record(), tmp_path)

    assert path.read_text(encoding="utf-8") == FIXTURE.read_text(encoding="utf-8")


def test_the_fixture_loads():
    loaded = load_run(FIXTURE)

    assert loaded.run_id == "2026-11-09_2026-11-15"
    assert loaded.schema_version == RUN_SCHEMA_VERSION


def test_the_committed_example_run_loads():
    # A fresh clone opens the web view and the MCP server on this file, with no API key.
    loaded = load_run(EXAMPLE)

    assert loaded.run_id == "2026-11-09_2026-11-15"
    assert [n.rank for n in loaded.notices if n.rank] == list(range(1, 8))


def test_save_then_load_gives_the_same_record(tmp_path):
    original = record()

    path = save_run(original, tmp_path)

    assert path.name == "2026-11-09_2026-11-15.json"
    assert load_run(path) == original


def test_saving_the_same_week_again_replaces_the_file(tmp_path):
    save_run(record(), tmp_path)
    cheaper = record().model_copy(update={"cost_usd": 0.01})

    path = save_run(cheaper, tmp_path)

    assert list(tmp_path.iterdir()) == [path]
    assert load_run(path).cost_usd == 0.01


def test_run_summary_and_model_are_copied():
    saved = record()

    assert (saved.date_from, saved.date_to) == (RUN.date_from, RUN.date_to)
    assert saved.generated_at == RUN.generated_at
    assert saved.model == MODEL
    assert (saved.tender_count, saved.prefilter_kept, saved.planning_count) == (463, 5, 12)
    assert (saved.complete, saved.problem) == (True, None)
    assert (saved.llm_calls, saved.cost_usd) == (7, 0.0412)


def test_notices_follow_the_report_order_and_ranks():
    csv_rows = list(csv.DictReader(io.StringIO(render_csv(scored_results(), RATIONALES))))

    saved = record()

    assert [(n.notice_id, n.outcome) for n in saved.notices] == [
        (row["notice_id"], row["outcome"]) for row in csv_rows
    ]
    assert [n.rank for n in saved.notices] == [1, 2, None, None, None]


def test_every_assessed_notice_is_present_with_its_reason():
    results = scored_results()

    saved = record(results)

    reasons = {n.notice_id: (n.outcome, n.reason) for n in saved.notices}
    assert reasons == {r.notice.notice_id: (r.outcome, r.reason) for r in results}


def test_notices_dropped_by_the_prefilter_are_counted_not_listed():
    saved = record()

    assert saved.prefilter_kept == 5
    assert len(saved.notices) == 5
    assert saved.tender_count == 463


def test_rationale_only_on_shortlisted_notices():
    rationales = {r.notice.notice_id: "A rationale." for r in scored_results()}

    saved = record(rationales=rationales)

    for notice in saved.notices:
        expected = "A rationale." if notice.outcome == SHORTLISTED else None
        assert notice.rationale == expected


def test_shortlisted_notice_carries_its_best_lot_and_score():
    saved = record()

    top = saved.notices[0]
    assert (top.notice_id, top.best_lot_id, top.score) == ("100002-2026", "1", 0.95)
    assert [lot.lot_id for lot in top.lots] == ["1", "2"]
    gated = top.lots[1]
    assert (gated.status, gated.reasons) == ("gated", ["main service is clinical cleaning"])


def test_notice_without_a_scored_lot_has_no_score():
    saved = record()

    unscored = [n for n in saved.notices if n.outcome != SHORTLISTED]
    assert all(n.score is None and n.best_lot_id is None for n in unscored)


def test_red_flags_keep_their_quote():
    saved = record()

    assert [(f.kind, f.quote) for f in saved.notices[0].red_flags] == [("tupe", "TUPE applies")]
    assert saved.notices[1].red_flags == []


def test_criteria_take_their_weight_from_the_profile():
    profile = profile_with(weights=PROFILE.scoring.weights.model_copy(update={"service": 0.5}))

    saved = record(profile=profile)

    weights = profile.scoring.weights.model_dump()
    criteria = [c for n in saved.notices for lot in n.lots for c in lot.criteria]
    assert criteria
    assert all(c.weight == weights[c.name] for c in criteria)
    assert saved.notices[0].lots[0].criteria[0].weight == 0.5


def test_profile_snapshot_is_taken_from_the_profile():
    snapshot = record().profile

    assert snapshot.offered_services == PROFILE.services.offered_names
    assert snapshot.excluded_services == PROFILE.services.excluded_names
    assert snapshot.region_nuts_codes == PROFILE.region.nuts_codes
    assert (snapshot.value_min_gbp, snapshot.value_max_gbp) == (
        PROFILE.value.min_gbp,
        PROFILE.value.max_gbp,
    )
    assert snapshot.accreditations_held == PROFILE.accreditations.held
    assert snapshot.mobilisation_min_weeks == PROFILE.mobilisation.min_weeks
    assert snapshot.deadline_min_days == PROFILE.deadline.min_days
    assert snapshot.weights == PROFILE.scoring.weights.model_dump()
    assert snapshot.shortlist_threshold == RUN.threshold


def broken_json(data):
    return '{"schema_version": 1, "run_id": '


def without_title(data):
    del data["notices"][0]["title"]
    return json.dumps(data)


def with_version_2(data):
    data["schema_version"] = 2
    return json.dumps(data)


def with_unsafe_run_id(data):
    data["run_id"] = "../../secrets"
    return json.dumps(data)


def not_an_object(data):
    return json.dumps([data])


@pytest.mark.parametrize(
    ("corrupt", "reason"),
    [
        (broken_json, "not readable JSON"),
        (without_title, "notices.0.title"),
        (with_version_2, "schema version 2"),
        (with_unsafe_run_id, "run_id"),
        (not_an_object, "not a JSON object"),
    ],
)
def test_a_bad_run_file_raises_an_error_naming_the_file(tmp_path, corrupt, reason):
    path = tmp_path / "2026-11-09_2026-11-15.json"
    path.write_text(corrupt(json.loads(FIXTURE.read_text(encoding="utf-8"))), encoding="utf-8")

    with pytest.raises(RunFileError) as error:
        load_run(path)

    assert str(path) in str(error.value)
    assert reason in str(error.value)


def test_a_missing_run_file_raises_an_error_naming_the_file(tmp_path):
    path = tmp_path / "2026-11-09_2026-11-15.json"

    with pytest.raises(RunFileError, match="2026-11-09_2026-11-15.json"):
        load_run(path)


def test_list_runs_skips_other_files_and_puts_the_newest_week_first(tmp_path):
    for name in [
        "2026-11-02_2026-11-08.json",
        "2026-11-16_2026-11-22.json",
        "2026-11-09_2026-11-15.json",
        "2026-11-10_2026-11-15.json",
        "notes.json",
        "2026-11-09_2026-11-15.txt",
        "2026-13-01_2026-13-07.json",
        "2026-11-15_2026-11-09.json",
    ]:
        (tmp_path / name).write_text("{}", encoding="utf-8")
    (tmp_path / "2026-10-26_2026-11-01.json").mkdir()

    names = [path.name for path in list_runs(tmp_path)]

    assert names == [
        "2026-11-16_2026-11-22.json",
        "2026-11-10_2026-11-15.json",
        "2026-11-09_2026-11-15.json",
        "2026-11-02_2026-11-08.json",
    ]


def test_list_runs_of_a_missing_folder_is_empty(tmp_path):
    assert list_runs(tmp_path / "runs") == []


@pytest.mark.parametrize(
    ("text", "valid"),
    [
        ("2026-11-09_2026-11-15", True),
        ("2026-11-09_2026-11-09", True),
        ("2026-11-15_2026-11-09", False),
        ("2026-02-30_2026-03-01", False),
        ("../2026-11-09_2026-11-15", False),
        ("2026-11-09_2026-11-15.json", False),
        ("2026-11-09", False),
        ("", False),
    ],
)
def test_run_ids_are_from_and_to_dates(text, valid):
    assert is_run_id(text) is valid
