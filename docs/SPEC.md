# Spec

## Problem
A UK facilities-management company (cleaning, security, building maintenance; ~60% public-sector revenue) screens Find a Tender by hand. Three bid staff read 150–250 notices a week and spend about 1.5 days deciding what to bid for, and they still miss relevant tenders described in unexpected words.

## Users and use
The bid team, once a week. They run the tool for the last full week and open a Markdown report: a ranked shortlist with a score breakdown, deadline, link and a short rationale for each tender. They decide in under 15 minutes which notices to open in full. A CSV of the same data goes into their own tracker.

## What we build (in scope)
- **CLI** `uv run python -m app --from YYYY-MM-DD --to YYYY-MM-DD`. Both dates are inclusive (from 00:00:00 to 23:59:59).
- **Fetch:** tender-stage and planning-stage notices updated in the range, from the Find a Tender OCDS API, with paging, a timeout and bounded retries that honour `Retry-After` on 429/503. Releases are grouped by notice ID (`ocid`) and only the latest is kept; withdrawn or cancelled notices are dropped. A fetch that stops partway keeps what it has and marks the run incomplete.
- **Stored data:** `data/raw/` (git-ignored) holds a reduced notice: `parties[]` cut to organisation name and role, and emails and phone numbers masked in free text. Nothing else is stored or logged.
- **Pre-filter (code):** drops a notice when its deadline has passed, its stated value is under £100k, or none of its CPV codes (notice, items and lots) match the profile. A notice with no CPV code at all is kept. Planning-stage notices are counted, not shortlisted.
- **Extract (LLM):** per lot (or once for a notice without lots): services and the primary service, delivery region, contract length, mobilisation time, mandatory accreditations and red flags (TUPE, short deadline, closed framework call-off). Unknown is an allowed value. Fields that drive a gate carry a supporting quote from the notice. Output is validated by Pydantic.
- **Score (code):** each lot is gated and scored on all criteria from `config/profile.toml`: service fit, region, value band, accreditations, mobilisation and deadline. Each criterion gives 0–1 and a reason. Notice-wide requirements apply to every lot.
- **Hard gates:** value under £100k, an excluded service as the lot's primary service, or a mandatory accreditation the company lacks. The two LLM-driven gates only reject when the supporting quote is found in the notice text; otherwise the notice goes to "needs review". Over £5m and out of region lower the score but are not gates.
- **Lots:** one row per notice, showing its best eligible lot by name.
- **Shortlist:** a score threshold set in config and tuned on the eval set.
- **Explain (LLM):** a 2–3 sentence rationale per shortlisted tender, written from the extracted fields only.
- **Output:** `report.md` and `shortlist.csv`. The report has four groups: shortlisted, rejected after extraction, needs review (failed extraction or unsupported gate), and not processed (budget or fetch stopped). It also shows the planning-stage count, the run's LLM cost, an "incomplete" banner when that applies, and the OGL v3.0 attribution.
- **Cost control:** `llm.py` records token usage per call. Extractions are cached by notice ID and release date, the input text is capped, and the run stops calling the LLM before a configured budget is exceeded.
- **Eval:** about 30 real notices with bid / no-bid labels and expected field values, including some the pre-filter dropped. It reports TP/FP/FN, precision, recall, pre-filter recall and per-field accuracy, with deadlines judged against a frozen date.

## What we do not build (out of scope), and why
- Web UI, user accounts, email alerts and scheduling: the brief excludes them, and a CLI plus a file covers a weekly run.
- Downloading tender documents, writing bids, and any source other than Find a Tender: excluded by the brief.
- MCP server and incumbent lookup: these won't fit the 5-hour time box, so they go in the README's next steps.
- Per-lot rows: the team reads by notice, and per-lot rows multiply review time.
- A held-out test split: with about 30 cases the split would be too small to mean anything, so results are reported as preliminary.
- Removing personal names from free text: this can't be done reliably with simple rules; emails and phone numbers are masked.

## Data
- Find a Tender OCDS API (`/api/1.0/ocdsReleasePackages`): public, no key, OGL v3.0 (attribution in the report and README).
- Volume is unverified. The team reads 150–250 notices a week, but the API may return more. Slice 1 measures the fetched count, the pre-filter survivors and the cost of one extraction before anything depends on them.
- Field coverage varies. Slice 1 checks real responses before the code relies on `value`, `tenderPeriod.endDate`, lots, CPV and delivery addresses.
- Test fixtures are sanitised real notices.

## Success measure
- On the labelled set: shortlist **recall ≥ 80%** and **precision ≥ 60%**, plus per-field extraction accuracy. With about 30 cases, tuned on the same set, these are preliminary figures.
- A week's report can be reviewed in under 15 minutes. This is not measured here; the report states the shortlist size as a proxy.
- Every score can be traced to rubric lines, and every rationale uses only extracted fields.

## Constraints
- Time box 5 hours in total (about 3 of building). Python, uv, Anthropic Claude Sonnet through `src/app/llm.py`.
- Under USD 5 of LLM usage for a full weekly run plus the eval, including retries and label drafting.
- Runs from a fresh clone using the README commands. Tests never call a real LLM or the live API.

## Assumptions
- Hard gates are as the client chose: value < £100k, excluded primary service, missing mandatory accreditation. Region and value over £5m are penalties only.
- A minor mention of an excluded service (for example, cleaning that includes a clinic) is a penalty, not a gate.
- Region comes from NUTS codes in delivery addresses when present (code), and from the text via the LLM otherwise. "North" means NUTS UKC, UKD and UKE.
- A national contract with no regional lot scores 0 on region but is not dropped.
- "New" means updated in the date range, so a notice amended this week appears again.
- The demo uses the most recent full Monday–Sunday week.
