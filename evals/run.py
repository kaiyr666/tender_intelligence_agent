"""Run the eval set through the whole pipeline: uv run python -m evals.run [--live]

Each line of evals/cases.jsonl labels one notice of evals/notices.json: bid or
no-bid, the lots the team would bid (`bid_lots`) and the expected extracted
fields of one lot. The harness pre-filters, extracts and scores the notices as
the CLI does, against a frozen date, and reports the shortlist's TP/FP/FN,
precision and recall, pre-filter recall, the lot check, per-field accuracy
with coverage, a threshold sweep and the LLM cost.

Extractions come from evals/extractions/, which is committed, so by default
the eval runs offline with no API key and makes no LLM calls (as in CI).
With --live, notices missing from it are read by the LLM in .env and saved.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.assess import assess
from app.config import get_settings
from app.extract import WHOLE_NOTICE, Extraction, ExtractionCache
from app.llm import ProviderError, Reply, Usage, get_provider
from app.notices import Notice
from app.prefilter import prefilter
from app.profile import Profile, load_profile
from app.score import ELIGIBLE, GATED, SHORTLISTED, NoticeResult, lot_regions

EVALS_DIR = Path(__file__).parent
CASES = EVALS_DIR / "cases.jsonl"
NOTICES = EVALS_DIR / "notices.json"
EXTRACTIONS = EVALS_DIR / "extractions"
# The model the committed extractions were made with; it is part of their cache key.
MODEL_FILE = EXTRACTIONS / "model.txt"
RESULTS = EVALS_DIR / "results" / "latest.json"

# Monday after the eval notices' week (9-15 Nov 2026), when the bid team runs the report.
# Deadlines are judged against this date, so the eval gives the same result on any day.
FROZEN_NOW = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
DROPPED = "dropped by pre-filter"
NOT_STATED = "not stated"
SWEEP_THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]


@dataclass(frozen=True)
class CaseRow:
    case_id: str
    case_set: str
    bid: bool
    outcome: str
    reason: str
    best_score: float | None  # the best eligible lot's score, for the threshold sweep
    best_lot: str | None
    chosen_lot_ok: bool | None  # None when no lot was chosen or the case is no-bid
    wrongly_gated_lots: list[str]
    field_hits: dict[str, bool]


class CachedOnly:
    """A provider for offline runs: every extraction must already be in evals/extractions."""

    usd_per_mtok = (0.0, 0.0)

    def __init__(self, model: str) -> None:
        self.model = model

    def complete(self, system: str, user: str) -> Reply:
        raise ProviderError(
            "an eval notice has no committed extraction for the current prompt and profile; "
            "run `uv run python -m evals.run --live` to read it"
        )


# Metrics


def confusion(rows: list[CaseRow]) -> dict:
    """Counts with "shortlisted" as the positive prediction; anything else is negative."""
    tp = sum(r.bid and r.outcome == SHORTLISTED for r in rows)
    fp = sum(not r.bid and r.outcome == SHORTLISTED for r in rows)
    fn = sum(r.bid and r.outcome != SHORTLISTED for r in rows)
    tn = len(rows) - tp - fp - fn
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, tp + fn),
    }


def sweep(
    rows: list[CaseRow], thresholds: list[float]
) -> list[tuple[float, float | None, float | None]]:
    """(threshold, precision, recall) if the shortlist were cut at each threshold instead.

    A notice is shortlisted exactly when its best eligible lot reaches the threshold,
    so re-deciding needs no new extraction.
    """
    results = []
    for threshold in thresholds:
        hit = [r.best_score is not None and r.best_score >= threshold for r in rows]
        tp = sum(h and r.bid for h, r in zip(hit, rows, strict=True))
        fp = sum(h and not r.bid for h, r in zip(hit, rows, strict=True))
        bids = sum(r.bid for r in rows)
        results.append((threshold, _ratio(tp, tp + fp), _ratio(tp, bids)))
    return results


def lot_check(bid_lots: list[str], result: NoticeResult | None) -> tuple[bool | None, list[str]]:
    """Whether the chosen lot is one the team would bid, and which bid lots were gated."""
    if result is None:
        return None, []
    gated = [lot.lot_id for lot in result.lots if lot.lot_id in bid_lots and lot.status == GATED]
    if not bid_lots or result.best_lot is None:
        return None, gated
    return result.best_lot.lot_id in bid_lots, gated


def same_requirements(expected: list[str], actual: list[str]) -> bool:
    """Equal sets of requirements; a "one of" group is compared as its set of schemes."""
    return {_scheme_set(name) for name in expected} == {_scheme_set(name) for name in actual}


def compare_fields(
    expected: dict, extraction: Extraction | None, notice: Notice
) -> dict[str, bool]:
    """Hit or miss per expected field for the expected lot; {} if that lot was not extracted.

    Region is the one the scorer uses (delivery addresses first), at NUTS 1, because that
    is what the region gate decides on; the LLM's reading counts only without them.
    """
    if extraction is None:
        return {}
    wanted_id = expected.get("lot_id") or WHOLE_NOTICE
    lot = next((x for x in extraction.lots if x.lot_id == wanted_id), None)
    if lot is None:
        return {}
    required = extraction.notice_mandatory_accreditations + lot.mandatory_accreditations
    notice_lot = next((n for n in notice.lots if n.lot_id == lot.lot_id), None)
    regions, _source = lot_regions(notice, notice_lot, lot)
    actual = {
        "primary_service": lot.primary_service,
        "services": lot.services,
        "region_nuts1": sorted({_nuts1(code) for code in regions}),
        "contract_length_months": lot.contract_length_months,
        "mobilisation_weeks": lot.mobilisation_weeks,
        "mandatory_accreditations": [r.name for r in required],
        "tupe": any(flag.kind == "tupe" for flag in extraction.red_flags),
    }
    return {
        field: _field_matches(field, value, actual[field])
        for field, value in expected.items()
        if field != "lot_id"
    }


def _field_matches(field: str, expected, actual) -> bool:
    if field == "primary_service":
        return _service_matches(expected, actual)
    if field == "services":
        return {_label(s) for s in expected} == {_label(s) for s in actual}
    if field == "region_nuts1":
        wanted = [] if expected == NOT_STATED else expected
        return sorted(r.upper() for r in wanted) == sorted(r.strip().upper() for r in actual)
    if field == "mandatory_accreditations":
        return same_requirements(expected, actual)
    if field == "tupe":
        return actual is (expected == "yes")
    if expected == NOT_STATED:
        return actual is None
    return actual is not None and abs(float(expected) - float(actual)) < 1e-6


def _service_matches(expected: str, actual: str | None) -> bool:
    if expected == NOT_STATED:
        return actual is None
    if expected == "other":
        return actual is not None and _label(actual).startswith("other")
    return actual is not None and _label(actual) == _label(expected)


def _nuts1(code: str) -> str:
    """'UKD42' -> 'UKD'; 'UK' stays 'UK'."""
    code = code.strip().upper()
    return code[:3] if code.startswith("UK") else code


def _scheme_set(name: str) -> frozenset[str]:
    """The schemes a requirement names, ignoring filler words and ISO edition years,
    so 'SSIP accreditation' and 'ISO 9001:2015' match 'SSIP' and 'ISO 9001'."""
    text = re.sub(r"^\s*one of\s*:", "", name.casefold())
    text = re.sub(r"\b(accreditation|accredited|certification|certified|registration)\b", "", text)
    text = re.sub(r"(iso\s*\d+)\s*:\s*\d{4}", r"\1", text)
    parts = re.split(r",|\bor\b", text)
    return frozenset(_compact(p) for p in parts if _compact(p) not in ("", "equivalent"))


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.casefold())


def _label(service: str) -> str:
    return service.strip().casefold()


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


# Running the pipeline


def load_cases(path: Path = CASES) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def load_notices(path: Path = NOTICES) -> list[Notice]:
    return [Notice.model_validate(n) for n in json.loads(path.read_text(encoding="utf-8"))]


def run_eval(cases: list[dict], notices: list[Notice], profile: Profile, provider, usage: Usage):
    """Pre-filter, extract and score the labelled notices; one CaseRow per case.

    Raises ProviderError when offline and an extraction is missing.
    """
    by_id = {n.notice_id: n for n in notices}
    labelled = [by_id[case["notice_id"]] for case in cases]
    screened = {s.notice.notice_id: s for s in prefilter(labelled, profile, FROZEN_NOW)}
    kept = [n for n in labelled if screened[n.notice_id].drop_reason is None]
    cache = ExtractionCache(EXTRACTIONS)
    results = {
        r.notice.notice_id: r for r in assess(kept, profile, FROZEN_NOW, provider, usage, cache)
    }
    return [
        _case_row(case, screened[case["notice_id"]].drop_reason, results.get(case["notice_id"]))
        for case in cases
    ]


def _case_row(case: dict, drop_reason: str | None, result: NoticeResult | None) -> CaseRow:
    chosen_ok, gated = lot_check(case["bid_lots"], result)
    if result is None:
        outcome, reason, best = DROPPED, drop_reason or "", None
    else:
        outcome, reason, best = result.outcome, result.reason, result.best_lot
    return CaseRow(
        case_id=case["notice_id"],
        case_set=case.get("set", "tuning"),
        bid=case["bid"],
        outcome=outcome,
        reason=reason,
        best_score=best.score if best and best.status == ELIGIBLE else None,
        best_lot=best.lot_id if best else None,
        chosen_lot_ok=chosen_ok,
        wrongly_gated_lots=gated,
        field_hits=compare_fields(case["expected"], result.extraction, result.notice)
        if result
        else {},
    )


def summarise(rows: list[CaseRow], threshold: float, usage: Usage, model: str) -> dict:
    sets = sorted({r.case_set for r in rows})
    return {
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "model": model,
        "frozen_now": FROZEN_NOW.isoformat(),
        "threshold": threshold,
        "llm_calls": usage.calls,
        "cost_usd": round(usage.cost_usd, 4),
        "by_set": {name: _set_summary([r for r in rows if r.case_set == name]) for name in sets},
        "all": _set_summary(rows),
    }


def _set_summary(rows: list[CaseRow]) -> dict:
    bids = [r for r in rows if r.bid]
    fields = sorted({f for r in rows for f in r.field_hits})
    return {
        "cases": len(rows),
        "bids": len(bids),
        **confusion(rows),
        "prefilter_recall": _ratio(sum(r.outcome != DROPPED for r in bids), len(bids)),
        "chosen_lot_ok": _ratio(
            sum(r.chosen_lot_ok is True for r in rows),
            sum(r.chosen_lot_ok is not None for r in rows),
        ),
        "fields": {
            f: {
                "accuracy": _ratio(
                    sum(r.field_hits.get(f) is True for r in rows),
                    sum(f in r.field_hits for r in rows),
                ),
                "coverage": _ratio(sum(f in r.field_hits for r in rows), len(rows)),
            }
            for f in fields
        },
        "sweep": sweep(rows, SWEEP_THRESHOLDS),
    }


def format_summary(summary: dict, rows: list[CaseRow]) -> str:
    lines = [
        f"Eval {summary['time']}, model {summary['model']}, judged at {summary['frozen_now']}",
        f"Threshold {summary['threshold']:.2f}; LLM calls {summary['llm_calls']}, "
        f"cost ${summary['cost_usd']:.2f}",
    ]
    for name, s in [*summary["by_set"].items(), ("all", summary["all"])]:
        lines += [
            "",
            f"## {name}: {s['cases']} cases, {s['bids']} bids",
            "| Metric | Value |",
            "|---|---|",
            f"| TP / FP / FN / TN | {s['tp']} / {s['fp']} / {s['fn']} / {s['tn']} |",
            f"| Precision | {_pct(s['precision'])} |",
            f"| Recall | {_pct(s['recall'])} |",
            f"| Pre-filter recall | {_pct(s['prefilter_recall'])} |",
            f"| Chosen lot is a bid lot | {_pct(s['chosen_lot_ok'])} |",
        ]
        lines += [
            f"| Field {f} | {_pct(v['accuracy'])} (coverage {_pct(v['coverage'])}) |"
            for f, v in s["fields"].items()
        ]
        lines.append(
            "| Sweep (threshold: precision / recall) | "
            + ", ".join(f"{t:.2f}: {_pct(p)} / {_pct(r)}" for t, p, r in s["sweep"])
            + " |"
        )
    lines += ["", "Cases the tool got wrong:"]
    lines += [_problem_line(r) for r in rows if _has_problem(r)]
    misses = [(r.case_id, f) for r in rows for f, hit in r.field_hits.items() if not hit]
    lines.append(f"Field misses: {', '.join(f'{c} {f}' for c, f in misses) or 'none'}")
    return "\n".join(lines)


def _has_problem(r: CaseRow) -> bool:
    wrong_outcome = r.bid != (r.outcome == SHORTLISTED)
    return wrong_outcome or r.chosen_lot_ok is False or bool(r.wrongly_gated_lots)


def _problem_line(r: CaseRow) -> str:
    label = "bid" if r.bid else "no-bid"
    line = f"- {r.case_id} ({label}, {r.case_set}): {r.outcome}, best lot {r.best_lot}"
    if r.chosen_lot_ok is False:
        line += ", lot not a bid lot"
    if r.wrongly_gated_lots:
        line += f", bid lots gated {', '.join(r.wrongly_gated_lots)}"
    return f"{line} | {r.reason}"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def prune_extractions(used: set[Path]) -> int:
    """Delete committed extractions no case uses any more (made with an older prompt or
    profile), so evals/extractions holds exactly what the eval reads. Git keeps history."""
    stale = [p for p in EXTRACTIONS.glob("*.json") if p not in used]
    for path in stale:
        path.unlink()
    return len(stale)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="evals.run", description=__doc__.splitlines()[0])
    parser.add_argument("--live", action="store_true", help="read missing extractions with the LLM")
    args = parser.parse_args()

    profile, cases, notices = load_profile(), load_cases(), load_notices()
    if args.live:
        provider = get_provider()
        usage = Usage(budget_usd=get_settings().budget_usd)
    else:
        provider = CachedOnly(MODEL_FILE.read_text(encoding="utf-8").strip())
        usage = Usage()
    try:
        rows = run_eval(cases, notices, profile, provider, usage)
    except ProviderError as error:
        sys.exit(f"Eval stopped: {error}")

    if args.live:
        MODEL_FILE.write_text(provider.model + "\n", encoding="utf-8")
        cache = ExtractionCache(EXTRACTIONS)
        by_id = {n.notice_id: n for n in notices}
        used = {cache.path_for(by_id[c["notice_id"]], profile, provider.model) for c in cases}
        removed = prune_extractions(used)
        print(f"Removed {removed} stale extraction files.")

    summary = summarise(rows, profile.scoring.shortlist_threshold, usage, provider.model)
    RESULTS.parent.mkdir(exist_ok=True)
    payload = {**summary, "rows": [asdict(r) for r in rows]}
    RESULTS.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(format_summary(summary, rows))


if __name__ == "__main__":
    main()
