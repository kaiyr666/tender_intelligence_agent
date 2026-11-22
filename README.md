# Tender Intelligence Agent

> Screens a week of UK public tenders and gives a facilities-management bid team a ranked, explained shortlist of the ones worth bidding for.

## The problem
A UK facilities-management company's bid team of three reads 150–250 new Find a Tender notices a week by hand. It costs them about a day and a half a week, and they still miss relevant tenders that are described in unexpected words. That time should go into writing bids.

## What is built
A command-line tool the bid team runs once a week. For a date range (by default the last full Monday–Sunday week) it:
- fetches the tender and planning notices updated in that range from the Find a Tender OCDS API, keeps the latest release of each notice and drops withdrawn ones. A fetch that stops partway keeps what it has and marks the report incomplete;
- stores a reduced copy of each notice in `data/raw/`, with contacts cut from `parties[]` and emails and phone numbers masked in the text;
- drops notices that are closed, under £100k or coded outside the company's work (CPV codes);
- has the LLM read each remaining notice once, lot by lot: services and the main service, region, contract length, mobilisation, mandatory accreditations and red flags, with a quote from the notice for the fields that can reject a lot;
- gates and scores every lot in code against `config/profile.toml` and keeps the best eligible lot per notice;
- has the LLM write a two-to-three-sentence rationale for each shortlisted notice from the scored fields only;
- writes `output/report.md` (shortlisted, rejected, needs review, not processed, with cost, planning count and OGL attribution) and `output/shortlist.csv` (every assessed notice and its outcome);
- saves the whole run as one validated JSON file, `output/runs/<from>_<to>.json`: the run summary, a snapshot of the profile, and every assessed notice with its lots, criteria, reasons, red flags and rationale (D37). The planned web view and MCP server read only this file.

Screening for another company means editing `config/profile.toml` (services with what they include and exclude, CPV codes, regions, accreditations held, weights, threshold), not the code. The eval harness (`evals/run.py`) and the blind-screen tool (`evals/blind.py`) are in `evals/`. Out of scope, and why: `docs/SPEC.md`.

## Run it
Needs [uv](https://docs.astral.sh/uv/); it installs Python 3.11 or later if missing.
```bash
uv sync
cp .env.example .env   # then add your API key to .env
uv run python -m app                                   # last full Monday–Sunday week
uv run python -m app --from 2026-11-09 --to 2026-11-15 # any range, both dates inclusive
```
With an OpenAI key, `.env` needs `OPENAI_API_KEY`, `LLM_PROVIDER=openai`, `LLM_MODEL=<model>`, and the model's price in USD per million tokens as `LLM_INPUT_USD_PER_MTOK` and `LLM_OUTPUT_USD_PER_MTOK`. The run refuses to start without a price, because the budget (`LLM_BUDGET_USD`, default 2.50) needs it. Claude works too: `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`.
A week takes about 3 minutes to fetch and, read from scratch, an estimated $0.60 in LLM calls (122 notices at about $0.005 each; the measured 9–15 Nov run paid $0.29 for the 62 notices not yet cached). Deadlines in the report and CSV are in UTC. The run writes `output/report.md`, `output/shortlist.csv` and `output/runs/<from>_<to>.json` (all git-ignored); a second run of the same week replaces its run file. `examples/runs/` holds one committed run (9–15 Nov) so the views can be tried without an API key. Extractions are cached in `data/cache/`, so a second run of the same week makes no extraction calls.

Tests: `uv run pytest` · Eval: `uv run python -m evals.run`. Neither needs an API key or the network: the eval reads committed extractions.

Data: contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/), from Find a Tender (https://www.find-tender.service.gov.uk).

## How it works
```
Find a Tender API → fetch, de-duplicate, sanitise → pre-filter → extract per lot → gate and score → rationale → report.md + shortlist.csv
     (code)                (code)                     (code)        (LLM)            (code)        (LLM)          (code)
```
The LLM does the two jobs that need reading: turning free text into fields, and writing the rationale. Everything that decides an outcome (the pre-filter, the hard gates, the scores, the threshold) is plain Python, so every score traces back to a rubric line and the same extraction always gives the same result (D1). The LLM's output is checked against a Pydantic model before use, and a gate that rests on the LLM's reading (an excluded main service, a missing accreditation) rejects only when its supporting quote is found in the notice; otherwise the notice goes to "needs review" (D8). The region gate is the exception: the client asked for out-of-region, UK-wide and unstated regions to be rejected outright (D25, D34). Cost is checked before every call against a budget (D10, D17). Every choice, with the alternatives it beat, is in [docs/DECISIONS.md](docs/DECISIONS.md).

## Results
Full figures and method in [docs/EVAL.md](docs/EVAL.md). Targets: recall ≥ 80%, precision ≥ 60%.

| Set | Cases (bids) | Precision | Recall | Note |
|---|---|---|---|---|
| Labelled, all | 42 (16) | 100% (15/15) | 94% (15/16) | every case has been used for fixes |
| Blind week 26 Oct–1 Nov, before D34 | 137 (4) | 60% (3/5) | 75% (3/4) | unseen, screened by the human, after review |
| Blind week, after D34 | 137 (4) | 75% (3/4) | 75% (3/4) | D34 was fixed on this week |

- The labelled figures show the fixes work, not how the tool does on a new week. The one unseen week has only four bids, so each one moves recall by 25 points.
- The one labelled miss (108109, Newcastle window cleaning) is the cost of the client's rule on national lots (D34): its lots are coded as all of England.
- Field accuracy on the 42: contract length and TUPE 100%, accreditations and mobilisation 97%, region 94%, main service 86%, services 81%.
- Cost: the 9–15 Nov week read 122 notices and shortlisted 7. 62 of them were new reads, for $0.29; the other 60 came from the cache. A fresh week is estimated at about $0.60. Re-reading all 42 eval notices costs about $0.20.
- The human's manual screen of the blind week (137 notices, already narrowed) took about 1 hour; the tool shortlisted 5 and reviewing its 10 disagreements took 15 minutes.

## Where it breaks
<!-- Honest limits: data it cannot handle, failure modes seen in the eval, what the reviews flagged and was not fixed. Write this yourself. -->
- **The eval numbers are preliminary.** 42 hand-picked cases, all now used for fixes: the 32 the profile and threshold were tuned on, and the 10 added afterwards, which scored 50% recall until the pre-filter was fixed on them (D32). Both reached 100% precision and recall after D32; since D34 the tuning set finds 7 of 8 bids and the check set 8 of 8 (15 of 16 in all). That says little about unseen weeks. One unseen week (26 Oct–1 Nov) was screened blind by the human (D33): after review the tool found 3 of 4 bids and 3 of its 5 shortlisted notices were bids (3 of 4 after D34, fixed on that week), but 4 bids is too few for a rate. D34 also costs one labelled bid on the tuning set (108109). Results in `docs/EVAL.md`.
- **Every construction-coded notice is read by the LLM** (D32), because buyers code repairs and maintenance as construction. That doubles a week's LLM reads (61 to 122 notices in 9–15 Nov; the 62 new reads cost $0.29), and keeping capital projects off the shortlist now rests on the LLM naming construction as the main service with a quote. In that week all the new notices were rejected. In the blind week it happened once: structural repairs to Blackpool Tower (engineering and structural steel codes) were read as building maintenance and shortlisted at 0.95.
- **Other CPV codes outside the profile are still dropped unread.** Fire-system and automatic-door servicing (50413100, 50330000) is dropped, which suits the client now that specialist M&E is out of scope (D27); a relevant notice coded only with an unrelated code is missed. In the blind week that was supply and installation of bin and scooter stores at Newcastle housing blocks (44000000), which the human judged a borderline bid.
- **A value of £0 is read as "not stated"** (D32), so it scores the neutral 0.5 rather than being dropped. A real contract of £0 (a concession paid by users) is treated the same way.
- **The committed eval extractions go stale on any prompt or profile change.** The offline eval and its test then fail until `uv run python -m evals.run --live` re-reads the 42 notices (about $0.20). This is deliberate: an eval silently scored on old extractions would mislead.
- **Personal names in free text are not removed.** Contact details in `parties[]` are dropped and emails and phone numbers in descriptions are masked, but a name written into a description stays.
- **Only the excluded-service and accreditation gates are checked against the notice text.** The region gate trusts the LLM's reading when a notice has no delivery address (D25), and other extracted fields (contract length, mobilisation) are validated for shape, not for truth.
- **The 15-minute review target is not measured.** No bid manager has timed a review of the report. As a baseline, the human's blind manual screen of 137 already narrowed notices took about 1 hour, and reviewing the tool's 10 disagreements took 15 minutes.
- **The blind screen cannot be rerun from a fresh clone.** Its marks and extractions are committed, but `evals.blind compare` also needs that week's notices, which live in the git-ignored `data/raw/`; fetching 26 Oct–1 Nov again rebuilds them, though notices amended since then will differ.
- **Phone masking over-masks.** Any 10–11 digit reference starting with 0 is masked as if it were a phone number.
- **Values in other currencies are treated as unknown.** One UK lot that week was labelled AED in the source data.
- **A week's fetch takes about 3 minutes,** because the API's stage filter is unreliable and every stage has to be fetched (D11).
- **Accreditation names are matched loosely.** A requirement for "Cyber Essentials Plus" counts as held because the company holds "Cyber Essentials". "X or equivalent" with only X named is treated as X, so "CHAS or equivalent" is rejected even though SafeContractor would qualify. Groups that name the alternatives ("CHAS, SafeContractor or Constructionline") are handled.
- **A lot that also covers any region outside the North is rejected** (D34, the client's rule for national lots). Buyers often list all 9 English regions for a local contract, so a northern tender coded that way is lost: 108109 (Newcastle window cleaning, a labelled bid) is rejected, and the 9–15 Nov shortlist went from 8 to 7. Lots across a regional border (Yorkshire and the East Midlands) are rejected too. The rule replaced "any northern code passes", which shortlisted EEM's national fire doors lot (100829) in the blind week.
- **Tenders outside the North are rejected, and so are UK-wide contracts and notices that do not say where the work is** (D25, the client's rule). A northern tender that does not state its region, or whose region the LLM misreads, is rejected without review. The LLM now also reads named places (D26), which brought back 106476 (Sheffield College, rejected at first because its notice has no delivery code). In the 9–15 Nov run the shortlist went from 28 before D25 to 9, to 8 after slice 4's profile changes (D28–D30), all of them labelled bids in the eval, and to 7 after D34; 6 notices are still rejected as "region not stated", mostly Scottish, Northern Irish or overseas buyers.
- **Borderline service classifications can flip between reads.** 107673 (minor works, joinery and redecoration, Merseyside) was "construction" in one extraction and "building maintenance" in the next. Each service now has written includes and excludes (D28), and on the eval re-read every bid lot was classed as the client would; the remaining service misses are out-of-scope notices (a Northern Ireland construction framework read as building maintenance, a food hall as "other" rather than catering), where another gate decides. The cache keeps a week's results repeatable, but any re-read can change them. Ties at 0.95 can also name a different best lot after a re-read.
- **Region no longer separates eligible lots.** Every eligible lot scores 1 on region, so a lot whose main service the company does not offer can reach 0.65. The threshold of 0.70 (D30) keeps such lots off the shortlist, but a bid lot with unknown value, unknown mobilisation and a short deadline can also fall under 0.70.
- **Specialist M&E is excluded by a label the LLM must apply.** HVAC, gas, heating, lifts and fire systems are an excluded service (D28) and M&E-only CPV codes no longer pass the pre-filter (D29), but a mixed lot is gated only when the LLM names M&E as its main service with a quote. Fire doors count as joinery, which the client does (check-set case 105640), so the line between them and fire systems rests on the LLM's reading.
- **Mobilisation is almost never stated,** so it scores 0.5 nearly everywhere and caps a lot's score at 0.95.
- **Staff checks and licences never gate** (DBS, CSCS, SIA licences, waste-carrier registration, Gas Safe, insurance; D22). A notice that truly depends on one the company cannot get is still shortlisted.
- **Red flags (TUPE, short deadline, closed framework call-off) are extracted but not scored.** A call-off only open to existing framework suppliers can still be shortlisted; the flag is there for the bid team to see.
- **Long notices are cut at 24,000 characters,** so the end of about one notice a week is never read. In 106942 lots 5a and 5b start after the cut and are scored from their titles alone; they are specialist M&E lots, rejected anyway. Raising the cap costs more per long notice (review 04).
- **A requirement quoted from one lot can gate another.** The quote check confirms the quote is in the notice, not that it belongs to the lot the LLM attached it to (review 04).
- **Lots listed twice by the LLM are both scored,** and the best of them counts. This has not been seen in the 122 notices of 9–15 Nov.
- **Notice-wide selection criteria are not passed to the LLM.** Lot-level criteria are; none of the 10 sample releases had criteria at notice level, so the gap is unconfirmed (review 04).
- **A `Retry-After` header given as a date is read as 10 seconds,** so a rate-limited fetch can retry early; after the last attempt it stops and keeps what it has.
- **A `--live` eval run that stops partway can still remove old extractions,** so the next offline eval fails until `--live` completes.
- **Lots the model leaves out are not scored.** If the extraction covers none of a notice's lots, the notice goes to "needs review"; if it covers some, the missing ones are ignored.
- **A provider error stops the run** (bad key, network). Extractions done so far are cached, so running again continues where it stopped.
- **The budget stops early rather than late.** Each call is checked against its worst case (full output allowance), so a run can stop with up to one call's maximum unspent.
- **Rationales are not checked in code.** The prompt gets only scored fields (D23) and the real week's 28 rationales matched them, but nothing verifies a number or place in the text. They also mostly restate the score breakdown.
- **Rationales are not cached.** Every run pays for them again (about $0.03 for a week).
- **A run file is only as fresh as its run.** Deadlines and the "closed" pre-filter are judged at the run date, so the committed 9–15 Nov example (run on 22 Nov) leaves out notices that closed between 15 and 22 Nov and differs from the report of a run on 16 Nov. An amended notice is re-read on the next run, so an old run file and a new one can disagree.
- **Run files hold notice text.** Titles, descriptions and quotes are stored as fetched, with emails and phone numbers masked (D14); a name written into a description stays, as in `data/raw/`. `output/` is git-ignored; the committed example was checked by the human first.
- **A schema change makes old run files unreadable.** A file with another `schema_version` is refused with an error naming the file, and has to be recreated by running that week again; there is no migration.
- **Scottish notices link to the Public Contracts Scotland API,** not a page a person can read, because that is the URL the source data gives.
- **The report shows the notice's total value,** not the best lot's; the lot's value is in the score breakdown.
- **Most scoring numbers are still first guesses** (unknown = 0.5, over £5m = 0.3, minor excluded service −0.25, the weights). Only the threshold (0.70) was set on the eval, and the eval is too small to tune the rest.

## Next steps (if this were a paid engagement)
<!-- What you would do next, in order, and why. Write this yourself. -->
1. A shadow pilot: the bid team runs the tool beside its manual screen for 3 to 4 weeks and records its own decision next to each CSV row. That gives about 20 to 30 real bid decisions on unseen weeks (about 60 would pin recall to within ±10 points) and times a real review of the report.
2. Separate structural and heritage repair from building maintenance in the service definitions, so a job like the Blackpool Tower repairs is gated as construction.
3. Apply the region gate in the pre-filter for notices with delivery addresses, so out-of-region notices cost no LLM call. Most of the reads D32 added are notices the region gate rejects anyway.
4. If the pilot shows the team missing local northern contracts coded "all of England", switch the region rule to D34's option (a), which keeps 108109.
5. Require supporting quotes for every extracted field, not only the gate fields.
6. Incumbent lookup from award notices. (The MCP server and a read-only web view are planned as slices 6–9 in `docs/PLAN.md`, D36.)

## How AI was used
Built with Claude Code under a written spec, plan and decisions log. Codex reviewed the spec and plan twice before any code was written (`docs/reviews/`); the code itself had no Codex review. The log of what was delegated, what the tests and reviews caught, and what the human overruled is in [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).
