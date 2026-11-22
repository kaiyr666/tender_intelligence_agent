"""Save each run's results as one validated JSON file, output/runs/<from>_<to>.json (D37).

The web view and the MCP server read only these files, never the pipeline. Text
from notices and the LLM is stored as it is; each reader escapes it for its own
output.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError, model_validator

from app.profile import Profile
from app.report import GROUPS, OUTPUT_DIR, RunSummary, grouped
from app.score import SHORTLISTED, LotResult, NoticeResult

RUN_SCHEMA_VERSION = 1
RUNS_DIR = OUTPUT_DIR / "runs"
RUN_ID_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}")

Outcome = Literal["shortlisted", "rejected", "needs review", "not processed"]


class RunFileError(Exception):
    """A run file that cannot be used: unreadable, invalid, or from another schema version."""


class CriterionRecord(BaseModel):
    name: str
    weight: float
    score: float
    reason: str


class LotRecord(BaseModel):
    lot_id: str
    lot_name: str
    status: Literal["eligible", "gated", "review"]
    reasons: list[str]
    score: float
    criteria: list[CriterionRecord]


class RedFlagRecord(BaseModel):
    kind: Literal["tupe", "short_deadline", "closed_framework_call_off"]
    quote: str


class NoticeRecord(BaseModel):
    notice_id: str
    ocid: str
    title: str
    buyer: str | None
    url: str
    published: datetime
    deadline: datetime | None
    value_gbp: float | None
    regions: list[str]
    cpv_codes: list[str]
    description: str | None
    outcome: Outcome
    reason: str
    rank: int | None  # 1..n on the shortlist, None elsewhere
    score: float | None  # of the best eligible lot
    best_lot_id: str | None
    lots: list[LotRecord]
    red_flags: list[RedFlagRecord]
    rationale: str | None  # shortlisted notices only


class ProfileSnapshot(BaseModel):
    """The parts of the profile a reader needs to understand the scores, as they were."""

    offered_services: list[str]
    excluded_services: list[str]
    region_nuts_codes: list[str]
    value_min_gbp: float
    value_max_gbp: float
    accreditations_held: list[str]
    mobilisation_min_weeks: int
    deadline_min_days: int
    weights: dict[str, float]
    shortlist_threshold: float


class RunRecord(BaseModel):
    schema_version: Literal[1]
    run_id: str
    date_from: date
    date_to: date
    generated_at: datetime
    model: str
    tender_count: int
    prefilter_kept: int
    planning_count: int
    complete: bool
    problem: str | None
    llm_calls: int
    cost_usd: float
    profile: ProfileSnapshot
    notices: list[NoticeRecord]

    @model_validator(mode="after")
    def _run_id_names_the_dates(self) -> "RunRecord":
        # The run ID becomes a file name, so it must be exactly the two dates.
        if self.run_id != run_id_for(self.date_from, self.date_to):
            raise ValueError("run_id must be <date_from>_<date_to>")
        return self


def run_id_for(date_from: date, date_to: date) -> str:
    return f"{date_from.isoformat()}_{date_to.isoformat()}"


def is_run_id(text: str) -> bool:
    """True for 'YYYY-MM-DD_YYYY-MM-DD' with real dates, from first. Check any ID from outside."""
    if not RUN_ID_PATTERN.fullmatch(text):
        return False
    try:
        date_from, date_to = (date.fromisoformat(part) for part in text.split("_"))
    except ValueError:
        return False
    return date_from <= date_to


def to_record(
    results: list[NoticeResult],
    rationales: dict[str, str],
    run: RunSummary,
    profile: Profile,
    model: str,
) -> RunRecord:
    """The run as one record, notices in the report's order. Pre-filter drops are only counted."""
    weights = profile.scoring.weights.model_dump()
    groups = grouped(results)
    notices = [
        _notice_record(result, rank, rationales, weights)
        for outcome, _ in GROUPS
        for rank, result in enumerate(groups[outcome], start=1)
    ]
    return RunRecord(
        schema_version=RUN_SCHEMA_VERSION,
        run_id=run_id_for(run.date_from, run.date_to),
        date_from=run.date_from,
        date_to=run.date_to,
        generated_at=run.generated_at,
        model=model,
        tender_count=run.tender_count,
        prefilter_kept=run.prefilter_kept,
        planning_count=run.planning_count,
        complete=run.complete,
        problem=run.problem,
        llm_calls=run.llm_calls,
        cost_usd=run.cost_usd,
        profile=_profile_snapshot(profile),
        notices=notices,
    )


def save_run(record: RunRecord, runs_dir: Path = RUNS_DIR) -> Path:
    """Write <run_id>.json into runs_dir, replacing an earlier run of the same dates."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / f"{record.run_id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


def load_run(path: Path) -> RunRecord:
    """Read and validate a run file. Raises RunFileError naming the file and what is wrong."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RunFileError(f"{path}: not readable JSON ({error})") from error
    if not isinstance(data, dict):
        raise RunFileError(f"{path}: not a JSON object")
    version = data.get("schema_version")
    if version != RUN_SCHEMA_VERSION:
        raise RunFileError(
            f"{path}: schema version {version}, but this tool reads version "
            f"{RUN_SCHEMA_VERSION}; run the CLI again for this week to rewrite it"
        )
    try:
        return RunRecord.model_validate(data)
    except ValidationError as error:
        raise RunFileError(f"{path}: not a valid run record ({_problems(error)})") from error


def list_runs(runs_dir: Path = RUNS_DIR) -> list[Path]:
    """Run files in runs_dir, the latest week (by its end date) first. Other files are skipped."""
    if not runs_dir.is_dir():
        return []
    paths = [path for path in runs_dir.glob("*.json") if path.is_file() and is_run_id(path.stem)]
    # ISO dates sort as text; the stem is "<from>_<to>", so sort on (to, from).
    return sorted(paths, key=lambda path: path.stem.split("_")[::-1], reverse=True)


def _notice_record(
    result: NoticeResult, rank: int, rationales: dict[str, str], weights: dict[str, float]
) -> NoticeRecord:
    notice, best = result.notice, result.best_lot
    shortlisted = result.outcome == SHORTLISTED
    red_flags = result.extraction.red_flags if result.extraction else []
    return NoticeRecord(
        notice_id=notice.notice_id,
        ocid=notice.ocid,
        title=notice.title,
        buyer=notice.buyer,
        url=notice.url,
        published=notice.published,
        deadline=notice.deadline,
        value_gbp=notice.value_gbp,
        regions=notice.regions,
        cpv_codes=notice.cpv_codes,
        description=notice.description,
        outcome=result.outcome,
        reason=result.reason,
        rank=rank if shortlisted else None,
        score=best.score if best else None,
        best_lot_id=best.lot_id if best else None,
        lots=[_lot_record(lot, weights) for lot in result.lots],
        red_flags=[RedFlagRecord(kind=flag.kind, quote=flag.quote) for flag in red_flags],
        rationale=rationales.get(notice.notice_id) if shortlisted else None,
    )


def _lot_record(lot: LotResult, weights: dict[str, float]) -> LotRecord:
    return LotRecord(
        lot_id=lot.lot_id,
        lot_name=lot.lot_name,
        status=lot.status,
        reasons=lot.reasons,
        score=lot.score,
        criteria=[
            CriterionRecord(name=c.name, weight=weights[c.name], score=c.score, reason=c.reason)
            for c in lot.criteria
        ],
    )


def _profile_snapshot(profile: Profile) -> ProfileSnapshot:
    return ProfileSnapshot(
        offered_services=profile.services.offered_names,
        excluded_services=profile.services.excluded_names,
        region_nuts_codes=profile.region.nuts_codes,
        value_min_gbp=profile.value.min_gbp,
        value_max_gbp=profile.value.max_gbp,
        accreditations_held=profile.accreditations.held,
        mobilisation_min_weeks=profile.mobilisation.min_weeks,
        deadline_min_days=profile.deadline.min_days,
        weights=profile.scoring.weights.model_dump(),
        shortlist_threshold=profile.scoring.shortlist_threshold,
    )


def _problems(error: ValidationError, limit: int = 3) -> str:
    """Where validation failed, without echoing the file's values (they are notice text)."""
    problems = [
        f"{'.'.join(str(part) for part in item['loc']) or 'record'}: {item['msg']}"
        for item in error.errors(include_url=False)
    ]
    more = f"; and {len(problems) - limit} more" if len(problems) > limit else ""
    return "; ".join(problems[:limit]) + more
