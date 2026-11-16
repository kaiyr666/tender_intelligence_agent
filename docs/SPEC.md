# Spec

## Problem
A UK facilities-management company (cleaning, security, building maintenance; ~60% public-sector revenue) screens Find a Tender by hand. Three bid staff read 150–250 notices a week and spend about 1.5 days deciding what to bid for, and they still miss relevant tenders described in unexpected words.

## Users and use
The bid team, once a week. They run the tool for the last full week and open a Markdown report: a ranked shortlist with a score breakdown, deadline, link and a short rationale for each tender. They decide in under 15 minutes which notices to open in full. A CSV of the same data goes into their own tracker.

## What we build (in scope)
- **CLI** `uv run python -m app --from YYYY-MM-DD --to YYYY-MM-DD`.
- **Fetch:** tender-stage notices from the Find a Tender OCDS API, with paging and `Retry-After` on 429/503. Saved to `data/raw/` (git-ignored) with `parties[]` reduced to organisation name and role. No contact names, emails or phones are kept.
- **Pre-filter (code):** relevant CPV codes, notice already closed, stated value under £100k. Planning-stage notices are counted, not shortlisted.
- **Extract (LLM):** from the title, description and lots: services, delivery region, contract length, mobilisation time, required accreditations and red flags (TUPE, short deadline, closed framework call-off). The output is validated by Pydantic.
- **Score (code):** a weighted rubric from `config/profile.toml`: service fit, region, value band, accreditations, mobilisation and deadline. Each criterion scores 0–1 with a reason. Hard gates: value under £100k, an excluded service as the main scope, or a required accreditation the company lacks. Over £5m and out of region lower the score but are not gates.
- **Lots:** one row per notice, scored on its best-fitting lot. Region and value come from that lot when it states them, and the report names the lot.
- **Shortlist:** a score threshold set in config and tuned on the eval set.
- **Explain (LLM):** a 2–3 sentence rationale per shortlisted tender, written from the extracted fields only.
- **Output:** `report.md` and `shortlist.csv`. The report also lists notices that passed the pre-filter but were rejected after extraction and scoring, the planning-stage count, and the OGL v3.0 attribution.
- **Eval:** about 30 real notices labelled bid / no-bid. It reports shortlist precision and recall and the accuracy of extracted fields.

## What we do not build (out of scope), and why
- Web UI, user accounts, email alerts and scheduling: the brief excludes them, and a CLI plus a file covers a weekly run.
- Downloading tender documents, writing bids, and any source other than Find a Tender: excluded by the brief.
- MCP server and incumbent lookup: these won't fit the 5-hour time box, so they go in the README's next steps.
- Per-lot rows: the team reads by notice, and per-lot rows multiply LLM calls and review time.

## Data
- Find a Tender OCDS API (`/api/1.0/ocdsReleasePackages`): public, no key, OGL v3.0 (attribution in the report and README). Volume is 150–250 new notices a week, before the pre-filter.
- Field coverage varies. Slice 1 checks real responses before the code relies on `value`, `tenderPeriod.endDate`, lots and delivery addresses.
- Personal data: `parties[]` contacts are dropped when the data is fetched and are never stored or logged. Test fixtures are sanitised real notices.

## Success measure
- On the labelled set: shortlist **recall ≥ 80%** and **precision ≥ 60%**, plus per-field extraction accuracy.
- A week's report can be reviewed in under 15 minutes. Proxy: the shortlist is short and each row fits on one screen.
- Every score can be traced to rubric lines, and every rationale uses only extracted fields.

## Constraints
- Time box 5 hours in total (about 3 of building). Python, uv, Anthropic Claude Sonnet through `src/app/llm.py`.
- Under USD 5 of LLM usage for a full weekly run plus the eval.
- Runs from a fresh clone using the README commands. Tests never call a real LLM or the live API.

## Assumptions
- Hard gates are as the client chose: value < £100k, excluded service as the main scope, missing accreditation. Region and value over £5m are penalties only.
- "Main scope" is excluded when the LLM marks the excluded service as the primary service. A minor mention (for example, cleaning that includes a clinic) is a penalty, not a gate.
- Region comes from NUTS codes in delivery addresses when present (code), and from the text via the LLM otherwise. "North" means NUTS UKC, UKD and UKE.
- A national contract with no regional lot scores 0 on region but is not dropped.
- Accreditations the company does not hold count as "missing" only when the notice says they are mandatory.
- The demo uses the most recent full Monday–Sunday week.
