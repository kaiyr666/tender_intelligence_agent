# Demo script, 23 Nov

Both views read the committed runs in `examples/runs/`, so nothing on the call needs the screening API key, the screening LLM or Find a Tender. Claude Desktop itself is an LLM service: if it is down, show the pre-rendered page and the written answers below. A live run takes about 16 minutes; do not start one on the call.

## Before the call
1. Render the page: `uv run python -m app.html_report examples/runs/2026-11-16_2026-11-21.json`, then open `output/report_2026-11-16_2026-11-21.html`.
2. Connect Claude Desktop to the MCP server with `--runs-dir examples/runs` (README, "Ask an AI assistant"), restart it, and check that the five tools are listed.
3. Run the four questions below once, against a timer.

## The week
16–21 Nov (Monday to Saturday; D40), run on 22 Nov, unlabelled. 489 tender notices, 125 kept by the pre-filter and read by the LLM, 8 shortlisted, 117 rejected, none needing review, $0.61. Rejections: 101 on region (85 out of region, 7 UK-wide, 5 partly outside the North, 4 not stated), 9 construction, 2 specialist M&E, 1 missing accreditation, 4 below the threshold.

## Questions and the rehearsal's answers
Rehearsed on 22 Nov with headless Claude Code (`claude -p`) over the MCP server. Every answer matched the run file (`examples/runs/2026-11-16_2026-11-21.json`). The shortlist and 109921's region rejection also appear in that run's `report.md`. The 0.75 score without the region gate and the TUPE flags on rejected notices appear only in the run file, so only the MCP server shows them; the web view lists rejected notices with their reason alone. The hard-gate rules in answer 4 come from the `get_profile` tool's description.

1. **What is on this week's shortlist, and why is the top one ranked first?** Eight notices: Port of Workington security, Kirklees electrical works (lot 2), Durham window cleaning, ACIS communal cleaning (lot 2) and WYFRA grounds maintenance at 0.95; Habinteg communal cleaning 0.92; L&Q reactive repairs NW North 0.88; NEPO retrofit 0.84. The assistant said Workington is first only because it was read first: five notices tie at 0.95 and ties are not broken. *Weak:* the honest answer to "why first" is "no reason". Say so before the client asks.
2. **Why was 109921-2026 rejected?** THEP schools cleaning: the delivery address is in Inner London East, so the region gate rejects it; without the gate it would have scored 0.75. It also carries a TUPE flag.
3. **Which shortlisted tenders carry TUPE?** None. The 8 shortlisted notices have no red flags, and their text does not mention TUPE (checked against the raw notices). Six rejected notices do. *Weak:* "none" makes a dull answer. Ask "which tenders in this run carry TUPE?" instead.
4. **What does the profile screen for?** Services offered and excluded, the three northern regions, £100k–£5m, accreditations held, 8 weeks' mobilisation, 14 days to respond, the weights and the 0.70 threshold, and which gates reject outright. Read from the run's own profile snapshot.

## Points a client may raise
- **Habinteg (109415):** 10 days to respond against 14 needed, scored 0.73 on deadline, but no short-deadline red flag. The assistant noticed the mismatch unprompted. The flag is the LLM's reading; the score is code ("Where it breaks").
- **Kirklees lot 2, full rewires:** classed as building maintenance, because general electrical maintenance counts as building maintenance (D27). Whether the company does domestic rewires is the bid team's call.
- **NEPO retrofit (109811), lot 5, building fabric:** a £500m framework (the lot's value is £50m, scored 0.30 for being over £5m). Close to the Blackpool Tower case: fabric work read as maintenance.
- **L&Q (110359):** a London buyer, but lot 15 is North West only, so it passes the region gate.

## Fallbacks
- Claude Desktop cannot connect: show the web view, and run `uv run pytest tests/test_mcp_server.py` (it includes the protocol over real stdio).
- Claude itself is unavailable: show the pre-rendered page and read the answers above.
- The 16–21 Nov file fails to load: use the 9–15 Nov example (`examples/runs/2026-11-09_2026-11-15.json`), which the README's questions also cover.
