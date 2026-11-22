"""Render a saved run as one self-contained HTML page for the bid team (slice 8, D36, D39).

uv run python -m app.html_report examples/runs/2026-11-09_2026-11-15.json [--out PATH]

The page reads only the run record (app.runs): no pipeline, LLM or network. It
makes no requests of its own: CSS and JavaScript are inline and fonts are the
system's. Every notice and LLM string is third-party text, so each one goes
through html.escape, links are https only, and the script never writes HTML.
Without JavaScript every group is shown; the script only filters tables and
switches between groups.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

from app import runs

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output"
FIND_A_TENDER = "https://www.find-tender.service.gov.uk"
FIND_A_TENDER_NOTICE = FIND_A_TENDER + "/Notice/"
LICENCE_URL = "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/"
# Groups in the report's order: (outcome, heading, anchor id).
GROUPS = [
    ("shortlisted", "Shortlisted", "shortlist"),
    ("rejected", "Rejected", "rejected"),
    ("needs review", "Needs review", "needs-review"),
    ("not processed", "Not processed", "not-processed"),
]
# The same labels as report.py's; imported from there they would load the pipeline.
RED_FLAG_LABELS = {
    "tupe": "TUPE",
    "short_deadline": "short deadline",
    "closed_framework_call_off": "closed framework call-off",
}
LOT_STATUS_LABELS = {"eligible": "eligible", "gated": "gated", "review": "needs review"}
NUTS_NAMES = {"UKC": "North East", "UKD": "North West", "UKE": "Yorkshire and the Humber"}
SCORES_NOTE = "Scores come from code; the LLM only reads notices and writes the rationale."


def render_html(record: runs.RunRecord) -> str:
    """The whole page for one run. Pure: the same record always gives the same text."""
    by_outcome = {
        outcome: [n for n in record.notices if n.outcome == outcome] for outcome, _, _ in GROUPS
    }
    by_outcome["shortlisted"].sort(key=lambda notice: notice.rank or 0)
    title = f"Tender shortlist, {record.date_from} to {record.date_to}"
    parts = [
        "<!doctype html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{_text(title)}</title>",
        f"<style>{STYLE}</style>",
        "</head>",
        "<body>",
        '<a class="skip" href="#shortlist">Skip to the shortlist</a>',
        _header(record, title),
        "<main>",
        _banner(record),
        _funnel(record, by_outcome),
        _group_nav(by_outcome),
        _shortlist_section(by_outcome["shortlisted"], record),
        *(
            _table_section(outcome, heading, anchor, by_outcome[outcome])
            for outcome, heading, anchor in GROUPS[1:]
        ),
        _profile_section(record.profile),
        "</main>",
        _footer(),
        f"<script>{SCRIPT}</script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(part for part in parts if part) + "\n"


def write_html(record: runs.RunRecord, path: Path) -> Path:
    """Write the page to path, creating its folder, and return the path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(record), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m app.html_report", description="Render a saved run as an HTML page."
    )
    parser.add_argument("run_file", type=Path, help="a run file, e.g. examples/runs/<id>.json")
    parser.add_argument("--out", type=Path, help="default: output/report_<run_id>.html")
    args = parser.parse_args(argv)
    try:
        record = runs.load_run(args.run_file)
    except runs.RunFileError as error:
        sys.exit(f"Could not read the run: {error}")
    out = args.out or OUTPUT_DIR / f"report_{record.run_id}.html"
    print(f"Page: {write_html(record, out)}")


# Page sections


def _header(record: runs.RunRecord, title: str) -> str:
    return (
        '<header class="page-head">'
        '<p class="eyebrow">Tender Intelligence · weekly screen of Find a Tender</p>'
        f"<h1>{_text(title)}</h1>"
        f'<p class="meta">Generated {_time(record.generated_at)} · model {_text(record.model)}'
        " · results as of this time</p>"
        "</header>"
    )


def _banner(record: runs.RunRecord) -> str:
    """The same rules as report.md's INCOMPLETE banners, via RunRecord.incomplete_reasons."""
    reasons = record.incomplete_reasons
    if not reasons:
        return ""
    items = "".join(f"<li>{_text(reason)}</li>" for reason in reasons)
    return (
        '<div class="banner" role="alert"><p><strong>INCOMPLETE:</strong> this run is missing '
        f"notices. Run the CLI again for this week.</p><ul>{items}</ul></div>"
    )


def _funnel(record: runs.RunRecord, by_outcome: dict[str, list[runs.NoticeRecord]]) -> str:
    steps = [
        (record.tender_count, "tender notices fetched"),
        (record.prefilter_kept, "kept by the pre-filter (CPV code, value, deadline)"),
        (len(by_outcome["shortlisted"]), "shortlisted"),
    ]
    funnel = "".join(
        f'<li><span class="num">{count:,}</span> <span>{label}</span></li>'
        for count, label in steps
    )
    others = " · ".join(
        f"{heading.lower()} {len(by_outcome[outcome])}" for outcome, heading, _ in GROUPS[1:]
    )
    return (
        '<section class="summary" aria-labelledby="summary-h">'
        '<h2 id="summary-h" class="visually-hidden">Run summary</h2>'
        f'<ol class="funnel">{funnel}</ol>'
        f'<p class="muted">Of those kept: {others}. {record.planning_count:,} planning-stage '
        f"notices (counted, not screened). LLM cost ${record.cost_usd:.2f} "
        f"({record.llm_calls:,} calls).</p>"
        "</section>"
    )


def _group_nav(by_outcome: dict[str, list[runs.NoticeRecord]]) -> str:
    links = "".join(
        f'<li><a href="#{anchor}" data-group-tab>{heading} ({len(by_outcome[outcome])})</a></li>'
        for outcome, heading, anchor in GROUPS
    )
    return f'<nav class="groups" aria-label="Result groups"><ul>{links}</ul></nav>'


def _shortlist_section(notices: list[runs.NoticeRecord], record: runs.RunRecord) -> str:
    threshold = record.profile.shortlist_threshold
    intro = (
        f'<p class="muted">Each lot is scored 0 to 1 on six weighted criteria. A notice is '
        f"shortlisted when its best eligible lot scores at least {threshold:.2f}. Equal "
        "scores keep the order the notices were read in.</p>"
    )
    if notices:
        body = "".join(_card(notice, record) for notice in notices)
    else:
        body = '<p class="empty">None this week.</p>'
    return (
        '<section id="shortlist" class="group" data-group aria-labelledby="shortlist-h">'
        f'<h2 id="shortlist-h">Shortlisted ({len(notices)})</h2>{intro}{body}</section>'
    )


def _card(notice: runs.NoticeRecord, record: runs.RunRecord) -> str:
    best = next((lot for lot in notice.lots if lot.lot_id == notice.best_lot_id), None)
    score = notice.score or 0.0
    threshold = record.profile.shortlist_threshold
    lot_line = ""
    if best is not None and len(notice.lots) > 1:
        lot_line = _fact("Best lot", f"{_text(best.lot_name)} (of {len(notice.lots)} lots)")
    flags = dict.fromkeys(flag.kind for flag in notice.red_flags)
    chips = "".join(f'<li class="chip">{RED_FLAG_LABELS[kind]}</li>' for kind in flags)
    rationale = notice.rationale or "Rationale not written."
    return (
        f'<article class="card" id="{_text("n-" + notice.notice_id)}">'
        '<div class="card-head">'
        f'<span class="rank" aria-label="Rank {notice.rank}">{notice.rank}</span>'
        f"<div><h3>{_text(notice.title)}</h3>"
        f'<p class="buyer">{_text(notice.buyer or "Buyer not stated")}</p></div>'
        "</div>"
        f"{_score_bar(score, threshold)}"
        '<dl class="facts">'
        f"{lot_line}"
        f"{_fact('Deadline', _deadline(notice.deadline, record.generated_at))}"
        f"{_fact('Notice value', _value(notice.value_gbp))}"
        "</dl>"
        + (f'<ul class="chips" aria-label="Red flags">{chips}</ul>' if chips else "")
        + f'<p class="rationale">{_text(rationale)}</p>'
        f"{_breakdown(notice, best)}"
        f'<p><a class="open" href="{_text(_safe_url(notice))}">Open on Find a Tender'
        f'<span class="visually-hidden"> (notice {_text(notice.notice_id)})</span></a></p>'
        "</article>"
    )


def _score_bar(score: float, threshold: float) -> str:
    """A bullet bar: the fill is the score, the tick the threshold; both are also in text."""
    return (
        '<div class="score">'
        f'<span class="score-num">{score:.2f}</span>'
        f'<span class="bar" role="img" aria-label="Score {score:.2f} out of 1; shortlist '
        f'threshold {threshold:.2f}">'
        f'<span class="fill" style="width:{_percent(score)}%"></span>'
        f'<span class="tick" style="left:{_percent(threshold)}%"></span></span>'
        f'<span class="muted small">threshold {threshold:.2f}</span>'
        "</div>"
    )


def _breakdown(notice: runs.NoticeRecord, best: runs.LotRecord | None) -> str:
    """Score breakdown, other lots and red-flag quotes, folded so the card stays short."""
    parts = []
    if best is not None:
        rows = "".join(
            "<tr>"
            f'<td data-label="Criterion">{_text(c.name)}</td>'
            f'<td data-label="Weight" class="n">{c.weight:.2f}</td>'
            f'<td data-label="Score" class="n">{c.score:.2f}</td>'
            f'<td data-label="Reason">{_text(c.reason)}</td>'
            "</tr>"
            for c in best.criteria
        )
        parts.append(
            f"<h4>Best lot: {_text(best.lot_name)}</h4>"
            '<table class="criteria"><thead><tr><th scope="col">Criterion</th>'
            '<th scope="col" class="n">Weight</th><th scope="col" class="n">Score</th>'
            f'<th scope="col">Reason</th></tr></thead><tbody>{rows}</tbody></table>'
        )
    others = [lot for lot in notice.lots if best is None or lot.lot_id != best.lot_id]
    if others:
        items = "".join(
            f"<li><strong>{_text(lot.lot_name)}</strong>: {LOT_STATUS_LABELS[lot.status]}, "
            f"score {lot.score:.2f}"
            + (f" ({_text('; '.join(lot.reasons))})" if lot.reasons else "")
            + "</li>"
            for lot in others
        )
        parts.append(f"<h4>Other lots</h4><ul>{items}</ul>")
    if notice.red_flags:
        quotes = "".join(
            f"<li>{RED_FLAG_LABELS[flag.kind]}: <q>{_text(flag.quote)}</q></li>"
            for flag in notice.red_flags
        )
        parts.append(f"<h4>Red flags in the notice</h4><ul>{quotes}</ul>")
    return f"<details><summary>Score breakdown</summary>{''.join(parts)}</details>"


def _table_section(
    outcome: str, heading: str, anchor: str, notices: list[runs.NoticeRecord]
) -> str:
    head = f'<h2 id="{anchor}-h">{heading} ({len(notices)})</h2>'
    if not notices:
        body = '<p class="empty">None this week.</p>'
    else:
        rows = "".join(
            "<tr>"
            f'<td data-label="Notice"><a href="{_text(_safe_url(n))}">'
            f"{_text(n.notice_id)}</a></td>"
            f'<td data-label="Title">{_text(n.title)}</td>'
            f'<td data-label="Reason">{_text(n.reason)}</td>'
            "</tr>"
            for n in notices
        )
        body = (
            f'<div class="filter" hidden><label for="{anchor}-filter">Filter {heading.lower()}'
            f'</label><input type="search" id="{anchor}-filter" data-filter="{anchor}" '
            f'autocomplete="off"><span class="muted small" aria-live="polite"></span></div>'
            '<table class="stack"><thead><tr><th scope="col">Notice</th>'
            '<th scope="col">Title</th><th scope="col">Reason</th></tr></thead>'
            f"<tbody>{rows}</tbody></table>"
        )
    return (
        f'<section id="{anchor}" class="group" data-group aria-labelledby="{anchor}-h">'
        f"{head}{body}</section>"
    )


def _profile_section(profile: runs.ProfileSnapshot) -> str:
    def services(items: list[runs.ServiceRecord]) -> str:
        return "".join(
            f"<li><strong>{_text(s.name)}</strong>"
            + (
                f"<br><span class='muted'>includes {_text('; '.join(s.includes))}</span>"
                if s.includes
                else ""
            )
            + (
                f"<br><span class='muted'>excludes {_text('; '.join(s.excludes))}</span>"
                if s.excludes
                else ""
            )
            + "</li>"
            for s in items
        )

    regions = ", ".join(
        f"{_text(NUTS_NAMES.get(code, code))} ({_text(code)})" for code in profile.region_nuts_codes
    )
    weights = ", ".join(f"{_text(name)} {weight:.2f}" for name, weight in profile.weights.items())
    accreditations = ", ".join(_text(a) for a in profile.accreditations_held) or "none"
    return (
        '<section class="profile" aria-labelledby="profile-h">'
        '<h2 id="profile-h">What we screen for</h2>'
        '<p class="muted">The company profile as it was when this run was scored.</p>'
        '<div class="profile-grid">'
        f'<div><h3>Services offered</h3><ul class="plain">{services(profile.offered_services)}'
        "</ul></div>"
        f'<div><h3>Services excluded</h3><ul class="plain">'
        f"{services(profile.excluded_services)}</ul></div>"
        '<div><h3>Rules</h3><dl class="facts">'
        f"{_fact('Regions', regions + ' only; a lot that also covers another region is rejected')}"
        f"{_fact('Value band', f'£{profile.value_min_gbp:,.0f} to £{profile.value_max_gbp:,.0f}')}"
        f"{_fact('Accreditations held', accreditations)}"
        f"{_fact('Mobilisation', f'at least {profile.mobilisation_min_weeks} weeks')}"
        f"{_fact('Deadline', f'at least {profile.deadline_min_days} days to respond')}"
        f"{_fact('Weights', weights)}"
        f"{_fact('Shortlist threshold', f'{profile.shortlist_threshold:.2f}')}"
        "</dl></div>"
        "</div></section>"
    )


def _footer() -> str:
    return (
        '<footer class="page-foot">'
        f"<p>{SCORES_NOTE}</p>"
        "<p>Contains public sector information licensed under the "
        f'<a href="{LICENCE_URL}">Open Government Licence v3.0</a>, from '
        f'<a href="{FIND_A_TENDER}">Find a Tender</a>.</p>'
        "</footer>"
    )


# Small helpers


def _fact(label: str, value_html: str) -> str:
    """One <dt>/<dd> pair; value_html must already be escaped."""
    return f"<div><dt>{label}</dt><dd>{value_html}</dd></div>"


def _deadline(deadline: datetime | None, generated_at: datetime) -> str:
    if deadline is None:
        return "not stated"
    return f"{_time(deadline)} · {_days_left(deadline, generated_at)}"


def _days_left(deadline: datetime, generated_at: datetime) -> str:
    """Counted in UTC calendar days from when the run was made, so the page never changes."""
    days = (deadline.astimezone(UTC).date() - generated_at.astimezone(UTC).date()).days
    if days < 0:
        return "closed"
    if days == 0:
        return "closes today"
    return "1 day left" if days == 1 else f"{days} days left"


def _time(moment: datetime) -> str:
    return f"{moment.astimezone(UTC):%Y-%m-%d %H:%M} UTC"


def _value(value_gbp: float | None) -> str:
    return f"£{value_gbp:,.0f}" if value_gbp is not None else "not stated"


def _percent(fraction: float) -> str:
    return f"{max(0.0, min(1.0, fraction)) * 100:.0f}"


def _safe_url(notice: runs.NoticeRecord) -> str:
    """The notice's own link if it is https, else its Find a Tender page (never javascript:)."""
    parsed = urlsplit(notice.url.strip())
    if parsed.scheme == "https" and parsed.netloc:
        return notice.url.strip()
    return FIND_A_TENDER_NOTICE + quote(notice.notice_id, safe="")


def _text(text: str) -> str:
    """Third-party text made safe for HTML content and quoted attribute values."""
    return escape(text, quote=True)


STYLE = """
:root{--bg:#f8fafc;--card:#fff;--text:#0f172a;--head:#1e3a8a;--muted:#475569;--line:#e2e8f0;
--accent:#1e40af;--track:#e2e8f0;--fill:#1e40af;--tick:#0f172a;--chip-bg:#fef3c7;
--chip-text:#92400e;--alert-bg:#fef2f2;--alert-line:#dc2626;--alert-text:#991b1b;
--focus:#1e40af;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#0b1220;--card:#111a2e;--text:#e2e8f0;
--head:#bfdbfe;--muted:#a3b1c6;--line:#243049;--accent:#93c5fd;--track:#243049;--fill:#60a5fa;
--tick:#f8fafc;--chip-bg:#422006;--chip-text:#fcd34d;--alert-bg:#2a0f12;--alert-line:#f87171;
--alert-text:#fecaca;--focus:#93c5fd}}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,-apple-system,
"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;font-variant-numeric:tabular-nums}
main,.page-head,.page-foot{max-width:60rem;margin:0 auto;padding:0 16px}
h1,h2,h3,h4{color:var(--head);line-height:1.25;margin:0}
h1{font-size:1.75rem}h2{font-size:1.25rem;margin:2rem 0 .5rem}h3{font-size:1.0625rem}
h4{font-size:.9375rem;margin:1rem 0 .25rem}
a{color:var(--accent);text-underline-offset:2px}
a:focus-visible,summary:focus-visible,input:focus-visible{outline:3px solid var(--focus);
outline-offset:2px;border-radius:2px}
.skip{position:absolute;left:-999px;top:0;background:var(--card);padding:8px 12px}
.skip:focus{left:16px;top:8px}
.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);
white-space:nowrap}
.page-head{padding-top:2rem;padding-bottom:1rem}
.eyebrow{margin:0 0 .25rem;color:var(--muted);font-size:.875rem;text-transform:uppercase;
letter-spacing:.04em}
.meta,.muted{color:var(--muted)}.small{font-size:.875rem}
.banner{border:1px solid var(--alert-line);border-left-width:6px;background:var(--alert-bg);
color:var(--alert-text);padding:12px 16px;border-radius:6px;margin:0 0 1rem}
.banner p,.banner ul{margin:0}.banner ul{padding-left:1.25rem}
.funnel{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;list-style:none;padding:0;
margin:0 0 .5rem}
.funnel li{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.funnel .num{display:block;font-size:1.75rem;font-weight:650;color:var(--head)}
.groups ul{display:flex;flex-wrap:wrap;gap:8px;list-style:none;padding:0;margin:1.5rem 0 0}
.groups a{display:inline-block;padding:10px 14px;border:1px solid var(--line);border-radius:999px;
background:var(--card);text-decoration:none;min-height:44px}
.groups a[aria-current=true]{background:var(--accent);color:var(--bg);border-color:var(--accent)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;
margin:12px 0}
.card-head{display:flex;gap:12px;align-items:flex-start}
.rank{flex:none;width:2rem;height:2rem;border-radius:50%;background:var(--accent);
color:var(--bg);display:grid;place-items:center;font-weight:700}
.buyer{margin:.125rem 0 0;color:var(--muted)}
.score{display:flex;align-items:center;gap:12px;margin:12px 0}
.score-num{font-size:1.5rem;font-weight:700;color:var(--head);min-width:3.2rem}
.bar{position:relative;flex:1;height:10px;background:var(--track);border-radius:5px}
.fill{position:absolute;inset:0 auto 0 0;background:var(--fill);border-radius:5px}
.tick{position:absolute;top:-5px;bottom:-5px;width:2px;background:var(--tick)}
.facts{margin:0;display:grid;gap:4px 16px;
grid-template-columns:repeat(auto-fit,minmax(14rem,1fr))}
.facts div{min-width:0}.facts dt{font-size:.8125rem;color:var(--muted)}.facts dd{margin:0}
.chips{display:flex;flex-wrap:wrap;gap:6px;list-style:none;padding:0;margin:12px 0 0}
.chip{background:var(--chip-bg);color:var(--chip-text);font-size:.8125rem;font-weight:600;
padding:2px 10px;border-radius:999px}
.rationale{margin:12px 0}
details{border-top:1px solid var(--line);padding-top:8px;margin-top:8px}
summary{cursor:pointer;color:var(--accent);font-weight:600;padding:10px 0}
.open{font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.9375rem;background:var(--card)}
th,td{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid var(--line)}
th{font-size:.8125rem;color:var(--muted);font-weight:600}
td{overflow-wrap:anywhere}.n{text-align:right;white-space:nowrap}
table.criteria td{overflow-wrap:break-word}
.filter{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 8px}
.filter input{font:inherit;padding:8px 10px;min-height:44px;border:1px solid var(--muted);
border-radius:6px;background:var(--card);color:var(--text);flex:1;min-width:12rem}
.empty{color:var(--muted);font-style:italic}
.profile-grid{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr))}
.profile-grid h3{margin:.5rem 0}
.plain{list-style:none;padding:0;margin:0}.plain li{margin:0 0 8px}
.page-foot{margin-top:3rem;padding-top:1rem;padding-bottom:2rem;border-top:1px solid var(--line);
color:var(--muted);font-size:.875rem}
@media (max-width:640px){h1{font-size:1.375rem}
.funnel{grid-template-columns:1fr}.funnel li{display:flex;align-items:baseline;gap:8px}
.funnel .num{display:inline;font-size:1.25rem}
table.criteria th,table.criteria td{padding:6px 4px;font-size:.875rem}
table.stack thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
table.stack,table.stack tbody,table.stack tr,table.stack td{display:block;width:100%}
table.stack tr{border-bottom:1px solid var(--line);padding:6px 0}
table.stack td{border:0;padding:2px 8px;text-align:left}
table.stack td::before{content:attr(data-label);display:block;font-size:.75rem;
color:var(--muted)}}
@media (prefers-reduced-motion:no-preference){.groups a,summary{transition:background .15s}}
@media print{.skip,.groups,.filter{display:none!important}
[data-group][hidden]{display:block!important}
body{background:#fff;color:#000}.card{break-inside:avoid}
details>*{display:block}}
"""

# Only textContent, attributes and the hidden property: never innerHTML.
SCRIPT = """
(function () {
  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-group-tab]"));
  var groups = Array.prototype.slice.call(document.querySelectorAll("[data-group]"));
  function show(id) {
    groups.forEach(function (group) { group.hidden = group.id !== id; });
    tabs.forEach(function (tab) {
      tab.setAttribute("aria-current", tab.getAttribute("href") === "#" + id ? "true" : "false");
    });
  }
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function (event) {
      event.preventDefault();
      var id = tab.getAttribute("href").slice(1);
      show(id);
      history.replaceState(null, "", "#" + id);
    });
  });
  var target = location.hash ? document.getElementById(location.hash.slice(1)) : null;
  var start = target && target.closest("[data-group]");
  show(start ? start.id : "shortlist");
  if (target) { target.scrollIntoView(); }
  document.querySelectorAll("[data-filter]").forEach(function (input) {
    var box = input.parentNode;
    var status = box.querySelector("[aria-live]");
    var rows = document.querySelectorAll("#" + input.dataset.filter + " tbody tr");
    box.hidden = false;
    input.addEventListener("input", function () {
      var words = input.value.toLowerCase().split(/\\s+/).filter(Boolean);
      var shown = 0;
      rows.forEach(function (row) {
        var text = row.textContent.toLowerCase();
        var match = words.every(function (word) { return text.indexOf(word) !== -1; });
        row.hidden = !match;
        if (match) { shown += 1; }
      });
      status.textContent = words.length ? shown + " of " + rows.length + " shown" : "";
    });
  });
})();
"""


if __name__ == "__main__":
    main()
