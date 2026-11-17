"""Write the weekly output: output/report.md for reading, output/shortlist.csv for the tracker.

Plain code, no LLM: it lays out what scoring and the rationale step produced.
Titles, buyers and rationales come from third parties or the model, so they
are escaped before they go into Markdown, and spreadsheet formulas are
neutralised in the CSV.
"""

import csv
import io
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from app.score import NEEDS_REVIEW, NOT_PROCESSED, REJECTED, SHORTLISTED, NoticeResult

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
GROUPS = [
    (SHORTLISTED, "Shortlisted"),
    (REJECTED, "Rejected after extraction"),
    (NEEDS_REVIEW, "Needs review"),
    (NOT_PROCESSED, "Not processed"),
]
RED_FLAG_LABELS = {
    "tupe": "TUPE",
    "short_deadline": "short deadline",
    "closed_framework_call_off": "closed framework call-off",
}
CRITERIA = ["service", "region", "value", "accreditations", "mobilisation", "deadline"]
ATTRIBUTION = (
    "Contains public sector information licensed under the Open Government Licence v3.0, "
    "from Find a Tender (https://www.find-tender.service.gov.uk)."
)
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


@dataclass(frozen=True)
class RunSummary:
    """Everything the report states about the run, apart from the per-notice results."""

    date_from: date
    date_to: date
    generated_at: datetime
    tender_count: int
    prefilter_kept: int
    planning_count: int
    complete: bool
    problem: str | None
    llm_calls: int
    cost_usd: float
    threshold: float
    weights: dict[str, float]


def write_report(
    results: list[NoticeResult],
    rationales: dict[str, str],
    run: RunSummary,
    out_dir: Path = OUTPUT_DIR,
) -> tuple[Path, Path]:
    """Write report.md and shortlist.csv into out_dir and return their paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path, csv_path = out_dir / "report.md", out_dir / "shortlist.csv"
    report_path.write_text(render_report(results, rationales, run), encoding="utf-8")
    # The byte-order mark makes Excel read the file as UTF-8, so "£" survives.
    csv_path.write_text(render_csv(results, rationales), encoding="utf-8-sig", newline="")
    return report_path, csv_path


def render_report(results: list[NoticeResult], rationales: dict[str, str], run: RunSummary) -> str:
    groups = grouped(results)
    lines = [f"# Tender shortlist, {run.date_from} to {run.date_to}", ""]
    if not run.complete:
        lines += [
            f"> **INCOMPLETE:** the fetch stopped early ({_md(run.problem or 'unknown')}). "
            "Notices after that point are missing; run again for the full range.",
            "",
        ]
    lines += _summary(groups, run)
    for outcome, heading in GROUPS:
        lines += ["", f"## {heading} ({len(groups[outcome])})", ""]
        if not groups[outcome]:
            lines.append("None this week.")
        elif outcome == SHORTLISTED:
            for rank, result in enumerate(groups[outcome], start=1):
                lines += ([""] if rank > 1 else []) + _shortlist_entry(rank, result, rationales)
        else:
            lines += _outcome_table(groups[outcome])
    lines += ["", "---", "", ATTRIBUTION, ""]
    return "\n".join(lines)


def render_csv(results: list[NoticeResult], rationales: dict[str, str]) -> str:
    """One row per assessed notice, shortlisted first by rank, with its outcome."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        ["rank", "outcome", "score", "notice_id", "title", "buyer", "best_lot", "deadline"]
        + ["value_gbp"]
        + [f"score_{name}" for name in CRITERIA]
        + ["red_flags", "reason", "rationale", "url"]
    )
    groups = grouped(results)
    for outcome, _ in GROUPS:
        for rank, result in enumerate(groups[outcome], start=1):
            writer.writerow(
                [
                    _csv_cell(cell)
                    for cell in _csv_row(rank, result, rationales.get(result.notice.notice_id))
                ]
            )
    return buffer.getvalue()


def grouped(results: list[NoticeResult]) -> dict[str, list[NoticeResult]]:
    """Results by outcome. The shortlist is ranked by score; other groups keep their order."""
    groups = {outcome: [r for r in results if r.outcome == outcome] for outcome, _ in GROUPS}
    groups[SHORTLISTED].sort(key=lambda r: r.best_lot.score, reverse=True)
    return groups


def _summary(groups: dict[str, list[NoticeResult]], run: RunSummary) -> list[str]:
    weights = ", ".join(f"{name} {weight:.2f}" for name, weight in run.weights.items())
    counts = ", ".join(f"{heading.lower()} {len(groups[o])}" for o, heading in GROUPS)
    return [
        f"Generated {run.generated_at:%Y-%m-%d %H:%M} UTC.",
        "",
        f"- {run.tender_count} tender notices; {run.prefilter_kept} kept by the pre-filter "
        "(CPV code, value and deadline).",
        f"- Of those: {counts}.",
        f"- {run.planning_count} planning-stage notices (counted, not screened).",
        f"- LLM cost ${run.cost_usd:.2f} ({run.llm_calls} calls).",
        "",
        f"Each lot is scored 0 to 1 on six criteria, weighted {weights}. A notice is "
        f"shortlisted when its best eligible lot scores at least {run.threshold:.2f}.",
    ]


def _shortlist_entry(rank: int, result: NoticeResult, rationales: dict[str, str]) -> list[str]:
    notice, lot = result.notice, result.best_lot
    lines = [
        f"### {rank}. {_md(notice.title)} ({lot.score:.2f})",
        "",
        f"- [{notice.notice_id}]({notice.url}) · {_md(notice.buyer or 'buyer not stated')} · "
        f"deadline {_deadline(result)} · notice value {_value(result)}",
    ]
    if len(result.lots) > 1:
        lines.append(f"- Best lot: {_md(lot.lot_name)} (of {len(result.lots)} lots scored)")
    flags = _red_flags(result)
    if flags:
        lines.append(f"- Red flags: {flags}")
    rationale = rationales.get(notice.notice_id, "Rationale not written.")
    lines += ["", _md(rationale), "", "| Criterion | Score | Reason |", "|---|---|---|"]
    lines += [f"| {c.name} | {c.score:.2f} | {_md(c.reason)} |" for c in lot.criteria]
    return lines


def _outcome_table(results: list[NoticeResult]) -> list[str]:
    lines = ["| Notice | Title | Reason |", "|---|---|---|"]
    for result in results:
        notice = result.notice
        lines.append(
            f"| [{notice.notice_id}]({notice.url}) | {_md(notice.title)} | {_md(result.reason)} |"
        )
    return lines


def _csv_row(rank: int, result: NoticeResult, rationale: str | None) -> list:
    notice, lot = result.notice, result.best_lot
    scores = {c.name: f"{c.score:.2f}" for c in lot.criteria} if lot else {}
    return [
        rank if result.outcome == SHORTLISTED else "",
        result.outcome,
        f"{lot.score:.2f}" if lot else "",
        notice.notice_id,
        notice.title,
        notice.buyer or "",
        lot.lot_name if lot else "",
        notice.deadline.date().isoformat() if notice.deadline else "",
        f"{notice.value_gbp:.0f}" if notice.value_gbp is not None else "",
        *[scores.get(name, "") for name in CRITERIA],
        _red_flags(result),
        result.reason,
        rationale or "",
        notice.url,
    ]


def _deadline(result: NoticeResult) -> str:
    deadline = result.notice.deadline
    return deadline.date().isoformat() if deadline else "not stated"


def _value(result: NoticeResult) -> str:
    value = result.notice.value_gbp
    return f"£{value:,.0f}" if value is not None else "not stated"


def _red_flags(result: NoticeResult) -> str:
    if result.extraction is None:
        return ""
    kinds = dict.fromkeys(flag.kind for flag in result.extraction.red_flags)
    return ", ".join(RED_FLAG_LABELS[kind] for kind in kinds)


def _md(text: str) -> str:
    """Third-party or model text made safe for one line of Markdown: no HTML, links or pipes."""
    text = " ".join(text.split())
    for char in ("\\", "|", "[", "]"):
        text = text.replace(char, "\\" + char)
    # "&" stays readable: on its own it cannot open a tag.
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _csv_cell(cell) -> str:
    """Prefix text a spreadsheet would run as a formula, so it shows as plain text."""
    text = str(cell)
    return "'" + text if text.startswith(FORMULA_STARTS) else text
