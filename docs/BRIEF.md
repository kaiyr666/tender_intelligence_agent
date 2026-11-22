# Brief: Tender Intelligence Agent

## Client situation
The client is a UK facilities-management company: cleaning, security and building maintenance. It is owned by a mid-market private equity fund, and about 60% of its revenue comes from public-sector contracts. Growing public-sector revenue is one of three levers in the fund's value-creation plan.

Today a bid team of three people screens UK public tenders by hand. They read 150–250 new notices a week on Find a Tender, spend roughly a day and a half a week deciding which are worth bidding for, and still miss relevant tenders that are described in unexpected words. The commercial director wants the team to spend its time writing bids, not reading notices.

## The ask
Build a working proof of concept that, for a given date range, pulls new UK public tenders, decides which ones this company should consider bidding for, and explains why. The output is a ranked shortlist the bid team can act on in minutes.

## Company profile (what "a good fit" means)
- **Services:** office and commercial cleaning, manned guarding and security, planned and reactive building maintenance, integrated facilities management
- **Not offered:** clinical or hospital cleaning, construction and capital works, catering, IT services
- **Regions:** North of England (North West, North East, Yorkshire and the Humber); will consider national contracts only if they are split into regional lots
- **Contract size:** £100,000 to £5 million in total value; below £100k is not worth bidding, above £5m needs a partner
- **Accreditations held:** ISO 9001, ISO 14001, Cyber Essentials, SafeContractor, SIA Approved Contractor
- **Capacity:** can mobilise a new contract in 8 weeks or more; shorter mobilisation is a risk

Keep this profile in a config file, not in code, so it can be changed for another client.

## Data
- **Source:** the UK Find a Tender Service OCDS API: `https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages`. Public, no API key, Open Government Licence v3.0 (attribution required).
- **Parameters:** `updatedFrom` / `updatedTo` (format `YYYY-MM-DDTHH:MM:SS`), `stages` (`planning`, `tender`, `award`), `limit` (max 100), `cursor` for the next page. On HTTP 429 or 503, wait for the `Retry-After` header.
- **Useful fields:** `tender.title`, `tender.description`, `tender.value`, `tender.classification` (CPV code), `tender.lots[]`, `tender.items[]`, `tender.tenderPeriod.endDate` (bid deadline, where present), `tender.selectionCriteria`, `buyer`, `parties[]`.
- **Personal data:** notices include named contact people, emails and phone numbers in `parties[]`. Do not store or log these; keep organisation-level data only.
- Field coverage varies between notices. Check real responses before relying on any field.

## What we need to see
1. **Fetch** tender-stage notices for a date range and save them locally. Raw data stays out of git; a small sanitised sample goes into the tests.
2. **Pre-filter** with plain code: CPV codes relevant to the services, value band, and notices whose deadline has already passed.
3. **Extract** with an LLM, from the free-text title, description and lots: services required, region or delivery location, contract length, mobilisation time, required accreditations, and red flags (e.g. TUPE obligations, very short deadlines, framework call-offs only open to existing suppliers). Validated structured output.
4. **Score** with plain code: a weighted, explainable rubric against the company profile. Weights live in config. The LLM must not decide the score.
5. **Explain:** a two-to-three sentence rationale per shortlisted tender, written by the LLM from the extracted fields only.
6. **Output:** a ranked shortlist as a Markdown report and a CSV with score, key fields, deadline, link to the notice and rationale. Also list notices rejected only by the LLM step, so the team can sanity-check them.
7. **Evaluate:** a labelled set of about 30 real notices (bid / no-bid for this company), reporting precision and recall of the shortlist plus accuracy of the extracted fields.

**If time allows:** an MCP server exposing `search_tenders`, `get_tender` and `shortlist` so an AI assistant can answer ad-hoc questions (now planned, see the update below); and incumbent lookup (who won previous contracts from the same buyer for similar services, using award notices).

## Out of scope
User accounts, downloading tender documents from buyer portals, writing bids, email alerts and scheduling, any source other than Find a Tender.

## Success measures
- The shortlist on the labelled set reaches **recall of at least 80%** (we rarely miss a good tender) with **precision of at least 60%** (most shortlisted tenders are worth a look).
- A bid manager can review a week of notices from the report in under 15 minutes.
- Every score can be explained from the rubric, and every rationale only uses facts in the notice.

## Constraints
- **Time box:** 5 hours, including spec, build, evaluation and documentation.
- **Stack:** Python. LLM via the project's `src/app/llm.py` (Anthropic, Claude Sonnet).
- **Cost:** under USD 5 of LLM usage for a full run plus evaluation.
- **Must run** from a fresh clone with the commands in the README.

## Answers to likely questions
- **Who labels the eval set?** Claude drafts bid / no-bid labels with a one-line reason for 30 notices; I check and correct them before they are used.
- **Which date range for the demo?** The most recent full week.
- **What if a notice has no value stated?** Keep it, flag "value unknown", and score that criterion as neutral.
- **What if the deadline field is missing?** Treat it as unknown and flag it; don't drop the notice.
- **Planning-stage notices?** Exclude from the shortlist, but count them in the report as an early pipeline signal.

## Update, 22 Nov 2026: a read-only web view and an MCP server
"Web UI" was out of scope by our own choice when we scoped this proof of concept, to protect the 5-hour time box; no client asked for that limit. For a demo on 23 Nov the proof of concept gains two read-only ways to see a week's results:

- **A web view** for the bid team: one self-contained HTML page per run with the ranked shortlist, each score's breakdown, the rationale, and why every other notice was rejected or sent to review. It opens from a file, needs no server and works offline.
- **An MCP server** for an AI assistant (Claude Desktop or Claude Code): it answers questions such as "why was this tender rejected?" from the same saved results.

Both read one saved results file per run, so neither re-runs the pipeline or has its own copy of the scoring. Both stay read-only: they do not edit the company profile, start a run, call the LLM or record bid decisions. Those wait for a pilot.

What the bid team does with them:
- **Input:** a date range, given to the CLI (by default the last full Monday–Sunday week).
- **Configure:** nothing in the view. The profile stays in `config/profile.toml`, changed under review, because a change shifts every result and the eval. API keys stay in environment variables.
- **View:** the shortlist with score breakdowns, rationales, deadlines and red flags; the rejected, needs-review and not-processed notices with their reasons; the run's health (complete or not, LLM cost); what the profile screens for.

