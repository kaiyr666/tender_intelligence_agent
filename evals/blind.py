"""A blind screen of an unseen week: a person marks the notices they would bid, then the
tool's results for the same week are compared with those marks.

    uv run python -m evals.blind make data/raw/notices_<week>.json evals/blind/<week>.md --now <ISO>
    uv run python -m evals.blind compare data/raw/notices_<week>.json evals/blind/<week>.md \
        --now <ISO> [--live]

The list leaves out only what the client's own rules exclude without judgement (closed at
the screen date, a stated value under the minimum, delivery addresses all outside the North
or UK-wide) and notices already in the eval set. Notices the pre-filter would drop stay in,
so its misses show. The list shows notice facts only, never the tool's output, and comes in
a fixed random order so the tool's ranking cannot leak into it.
"""

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from app.assess import assess
from app.config import get_settings
from app.extract import ExtractionCache
from app.llm import ProviderError, Usage, get_provider
from app.notices import Notice
from app.prefilter import prefilter
from app.profile import Profile, load_profile
from app.score import ELIGIBLE, SHORTLISTED
from evals.run import DROPPED, CachedOnly, load_cases

BLIND_DIR = Path(__file__).parent / "blind"
EXTRACTIONS = BLIND_DIR / "extractions"

SHUFFLE_SEED = 2026
DESCRIPTION_CHARS = 300
MARKS = {"b": "bid", "m": "maybe", " ": "no", "": "no"}
# A reason may follow the notice id ("`105810-2026` — damp, gut feel"); it is read at review.
MARK_LINE = re.compile(r"^\[ *(\S?) *\] *\d+\. .*?`(\d+-\d{4})`(.*)$", re.MULTILINE)


@dataclass(frozen=True)
class Decision:
    """What the tool did with one notice: its outcome, why, and its best eligible score."""

    outcome: str
    reason: str
    score: float | None


def screening_list(
    notices: list[Notice], profile: Profile, now: datetime, exclude_ids: set[str]
) -> list[Notice]:
    """The notices a person has to judge, in a fixed random order."""
    chosen = [
        notice
        for notice in notices
        if notice.notice_id not in exclude_ids
        and not _closed(notice, now)
        and not _under_minimum(notice, profile)
        and not _outside_region_by_address(notice, profile.region.nuts_codes)
    ]
    random.Random(SHUFFLE_SEED).shuffle(chosen)
    return chosen


def to_markdown(notices: list[Notice], now: datetime) -> str:
    lines = [
        "# Blind screen",
        "",
        f"Open notices on {now:%d %b %Y}, delivered in the North, UK-wide by lot or with no "
        "stated region, whatever their CPV code. Mark each one as the bid team would:",
        "",
        "- `[b]` we would bid for it (or for one of its lots)",
        "- `[m]` maybe: we would open the notice to decide",
        "- `[ ]` leave blank: not for us",
        "",
        "Note how long the screen took.",
        "",
        "## Notices",
        "",
    ]
    for number, notice in enumerate(notices, start=1):
        lines += [f"[ ] {number}. {_headline(notice)}", f"    {_summary(notice)}", ""]
    return "\n".join(lines)


def parse_marks(text: str) -> dict[str, str]:
    """notice_id -> "bid", "maybe" or "no". An unknown mark is an error, not a guess."""
    marks = {}
    for mark, notice_id, _ in MARK_LINE.findall(text):
        if mark.lower() not in MARKS:
            raise ValueError(f"unknown mark [{mark}] for {notice_id}; use [b], [m] or [ ]")
        marks[notice_id] = MARKS[mark.lower()]
    return marks


def parse_reasons(text: str) -> dict[str, str]:
    """notice_id -> the reason written after it, without leading dashes."""
    reasons = {}
    for _, notice_id, after in MARK_LINE.findall(text):
        reason = after.strip().lstrip("—-").strip()
        if reason:
            reasons[notice_id] = reason
    return reasons


def decisions(
    notices: list[Notice],
    profile: Profile,
    now: datetime,
    provider,
    usage: Usage,
    cache: ExtractionCache | None,
) -> dict[str, Decision]:
    """Run the real pipeline (pre-filter, extract, score) on the screened notices."""
    screened = prefilter(notices, profile, now)
    found = {
        s.notice.notice_id: Decision(DROPPED, s.drop_reason, None)
        for s in screened
        if s.drop_reason
    }
    kept = [s.notice for s in screened if s.drop_reason is None]
    if kept:
        for result in assess(kept, profile, now, provider, usage, cache):
            best = result.best_lot
            score = best.score if best and best.status == ELIGIBLE else None
            found[result.notice.notice_id] = Decision(result.outcome, result.reason, score)
    return found


def tally(marks: dict[str, str], found: dict[str, Decision], maybe_is_bid: bool) -> dict[str, int]:
    """The person's bids the tool shortlisted (found) or not (missed), the tool's shortlist
    entries the person would not bid (noise), and notices both left out (agreed_no)."""
    counts = {"found": 0, "missed": 0, "noise": 0, "agreed_no": 0}
    for notice_id, mark in marks.items():
        is_bid = mark == "bid" or (maybe_is_bid and mark == "maybe")
        shortlisted = found[notice_id].outcome == SHORTLISTED
        if is_bid:
            counts["found" if shortlisted else "missed"] += 1
        else:
            counts["noise" if shortlisted else "agreed_no"] += 1
    return counts


def disagreements(marks: dict[str, str], found: dict[str, Decision]) -> list[str]:
    """Notices to review against the full text: every maybe, and every mismatch."""
    return [
        notice_id
        for notice_id, mark in marks.items()
        if mark == "maybe" or (mark == "bid") != (found[notice_id].outcome == SHORTLISTED)
    ]


def _closed(notice: Notice, now: datetime) -> bool:
    return notice.status == "complete" or (notice.deadline is not None and notice.deadline < now)


def _under_minimum(notice: Notice, profile: Profile) -> bool:
    return notice.value_gbp is not None and notice.value_gbp < profile.value.min_gbp


def _outside_region_by_address(notice: Notice, north: list[str]) -> bool:
    """True only when every lot has delivery codes and none is in the North, as the region
    gate would decide from the addresses alone (a lot without codes needs the text)."""
    if len(notice.lots) > 1:
        places = [lot.regions for lot in notice.lots]
    else:
        lot_regions = notice.lots[0].regions if notice.lots else []
        places = [lot_regions or notice.regions]
    if any(not codes for codes in places):
        return False
    return not any(code.startswith(tuple(north)) for codes in places for code in codes)


def _headline(notice: Notice) -> str:
    value = f"£{notice.value_gbp:,.0f}" if notice.value_gbp is not None else "value not stated"
    regions = set(notice.regions).union(*(lot.regions for lot in notice.lots))
    delivered = ", ".join(sorted(regions)) or "not stated"
    closes = f"{notice.deadline:%d %b %Y}" if notice.deadline else "not stated"
    lots = f" · {len(notice.lots)} lots" if len(notice.lots) > 1 else ""
    return (
        f"**{notice.title.strip()}** · {notice.buyer or 'buyer not stated'} · {value}"
        f" · delivered: {delivered} · closes: {closes}{lots} · `{notice.notice_id}`"
    )


def _summary(notice: Notice) -> str:
    text = " ".join((notice.description or "").split())
    if len(text) > DESCRIPTION_CHARS:
        text = text[:DESCRIPTION_CHARS].rsplit(" ", 1)[0] + " …"
    return f"{text} {notice.url}".strip()


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("make", help="write the screening list for a saved week")
    make.add_argument("notices", type=Path)
    make.add_argument("out", type=Path)
    make.add_argument("--now", type=datetime.fromisoformat, required=True)
    compare = commands.add_parser("compare", help="run the tool and compare with the marks")
    compare.add_argument("notices", type=Path)
    compare.add_argument("marks", type=Path)
    compare.add_argument("--now", type=datetime.fromisoformat, required=True)
    compare.add_argument("--live", action="store_true", help="read missing notices with the LLM")
    args = parser.parse_args()

    raw = json.loads(args.notices.read_text(encoding="utf-8"))
    notices = [Notice.model_validate(n) for n in raw]
    if args.command == "make":
        _make(notices, args)
    else:
        _compare(notices, args)


def _make(notices: list[Notice], args: argparse.Namespace) -> None:
    eval_ids = {case["notice_id"] for case in load_cases()}
    chosen = screening_list(notices, load_profile(), args.now, eval_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_markdown(chosen, args.now), encoding="utf-8")
    print(f"{len(chosen)} of {len(notices)} notices to screen: {args.out}")


def _compare(notices: list[Notice], args: argparse.Namespace) -> None:
    text = args.marks.read_text(encoding="utf-8")
    marks, reasons = parse_marks(text), parse_reasons(text)
    by_id = {n.notice_id: n for n in notices}
    screened = [by_id[notice_id] for notice_id in marks]
    model_file = EXTRACTIONS / "model.txt"
    if args.live:
        provider, usage = get_provider(), Usage(budget_usd=get_settings().budget_usd)
    else:
        provider, usage = CachedOnly(model_file.read_text(encoding="utf-8").strip()), Usage()
    try:
        found = decisions(
            screened, load_profile(), args.now, provider, usage, ExtractionCache(EXTRACTIONS)
        )
    except ProviderError as error:
        sys.exit(f"Compare stopped: {error}")
    if args.live:
        model_file.write_text(provider.model + "\n", encoding="utf-8")
    out = args.marks.with_name(args.marks.stem + "_results.md")
    out.write_text(results_markdown(marks, reasons, found, by_id, args.now, usage), "utf-8")
    print(f"LLM calls {usage.calls}, cost ${usage.cost_usd:.2f}. Results: {out}")


def results_markdown(
    marks: dict[str, str],
    reasons: dict[str, str],
    found: dict[str, Decision],
    by_id: dict[str, Notice],
    now: datetime,
    usage: Usage,
) -> str:
    """Counts both ways, then every disagreement with both sides' reasons, for review."""
    lines = [
        "# Blind screen results",
        "",
        f"Judged at {now:%d %b %Y %H:%M} UTC; {len(marks)} notices; "
        f"LLM calls {usage.calls}, cost ${usage.cost_usd:.2f}.",
        "",
        "| Maybes counted as | Found | Missed | Shortlisted, not marked | Agreed no |",
        "|---|---|---|---|---|",
    ]
    for label, maybe_is_bid in (("no", False), ("bid", True)):
        counts = tally(marks, found, maybe_is_bid)
        lines.append(
            f"| {label} | {counts['found']} | {counts['missed']} | {counts['noise']} "
            f"| {counts['agreed_no']} |"
        )
    lines += ["", "## To review against the full notice", ""]
    for number, notice_id in enumerate(disagreements(marks, found), start=1):
        notice, decision = by_id[notice_id], found[notice_id]
        score = f" ({decision.score:.2f})" if decision.score is not None else ""
        lines += [
            f"### {number}. {notice.title.strip()} (`{notice_id}`)",
            notice.url,
            f"- Your mark: {marks[notice_id]}"
            + (f" ({reasons[notice_id]})" if notice_id in reasons else ""),
            f"- Tool: {decision.outcome}{score}: {decision.reason}",
            "- Group: (tool error / missing rule / your slip / borderline)",
            "",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
