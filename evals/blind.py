"""A blind screen of an unseen week: a person marks the notices they would bid, then the
tool's results for the same week are compared with those marks.

    uv run python -m evals.blind make data/raw/notices_<week>.json evals/blind/<week>.md --now <ISO>

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
from datetime import datetime
from pathlib import Path

from app.notices import Notice
from app.profile import Profile, load_profile
from evals.run import load_cases

SHUFFLE_SEED = 2026
DESCRIPTION_CHARS = 300
MARKS = {"b": "bid", "m": "maybe", " ": "no", "": "no"}
# A reason may follow the notice id ("`105810-2026` — damp, gut feel"); it is read at review.
MARK_LINE = re.compile(r"^\[ *(\S?) *\] *\d+\. .*?`(\d+-\d{4})`.*$", re.MULTILINE)


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
    for mark, notice_id in MARK_LINE.findall(text):
        if mark.lower() not in MARKS:
            raise ValueError(f"unknown mark [{mark}] for {notice_id}; use [b], [m] or [ ]")
        marks[notice_id] = MARKS[mark.lower()]
    return marks


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
    args = parser.parse_args()

    raw = json.loads(args.notices.read_text(encoding="utf-8"))
    notices = [Notice.model_validate(n) for n in raw]
    eval_ids = {case["notice_id"] for case in load_cases()}
    chosen = screening_list(notices, load_profile(), args.now, eval_ids)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_markdown(chosen, args.now), encoding="utf-8")
    print(f"{len(chosen)} of {len(notices)} notices to screen: {args.out}")


if __name__ == "__main__":
    main()
