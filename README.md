# Tender Intelligence Agent

> Screens a week of UK public tenders and gives a facilities-management bid team a ranked, explained shortlist of the ones worth bidding for.

## The problem
A UK facilities-management company's bid team of three reads 150–250 new Find a Tender notices a week by hand. It costs them about a day and a half a week, and they still miss relevant tenders that are described in unexpected words. That time should go into writing bids.

## What is built
<!-- The working pieces, in plain words. What is deliberately not built: see docs/SPEC.md. -->

## Run it
```bash
uv sync
cp .env.example .env   # then add your API key to .env
uv run python -m app
```
With an OpenAI key, `.env` needs `OPENAI_API_KEY`, `LLM_PROVIDER=openai`, `LLM_MODEL=<model>`, and the model's price in USD per million tokens as `LLM_INPUT_USD_PER_MTOK` and `LLM_OUTPUT_USD_PER_MTOK`. The run refuses to start without a price, because the budget (`LLM_BUDGET_USD`, default 2.50) needs it.
The run writes `output/report.md` and `output/shortlist.csv` (git-ignored).
Tests: `uv run pytest` · Eval: `uv run python -m evals.run`

## How it works
```
<input> → <step> → <step> → <output>
```
<!-- Which steps are plain code and which use the LLM, and why. Details in docs/DECISIONS.md. -->

## Results
<!-- Headline numbers from docs/EVAL.md. -->

## Where it breaks
<!-- Honest limits: data it cannot handle, failure modes seen in the eval, what the reviews flagged and was not fixed. Write this yourself. -->
- **The eval numbers are preliminary.** About 30 cases, partly hand-picked, with the threshold tuned on the same set. There is no held-out set (plan reviews 01 and 02, not fixed; see D9).
- **Personal names in free text are not removed.** Contact details in `parties[]` are dropped and emails and phone numbers in descriptions are masked, but a name written into a description stays.
- **Only the excluded-service and accreditation gates are checked against the notice text.** The region gate trusts the LLM's reading when a notice has no delivery address (D25), and other extracted fields (contract length, mobilisation) are validated for shape, not for truth.
- **The 15-minute review target is not measured.** No bid manager has timed a real review.
- **The CPV pre-filter misses relevant work coded outside the profile.** For example, fire-system servicing (50413100) and automatic-door maintenance (50330000) are dropped before the LLM sees them.
- **Phone masking over-masks.** Any 10–11 digit reference starting with 0 is masked as if it were a phone number.
- **Values in other currencies are treated as unknown.** One UK lot that week was labelled AED in the source data.
- **A week's fetch takes about 3 minutes,** because the API's stage filter is unreliable and every stage has to be fetched (D11).
- **Accreditation names are matched loosely.** A requirement for "Cyber Essentials Plus" counts as held because the company holds "Cyber Essentials". "X or equivalent" with only X named is treated as X, so "CHAS or equivalent" is rejected even though SafeContractor would qualify. Groups that name the alternatives ("CHAS, SafeContractor or Constructionline") are handled.
- **A delivery-address list that covers most of England counts as in region.** A lot passes the region gate when any delivery code is in the North, so a notice listing every English region passes like a northern one, although UK-wide contracts are meant to be rejected. Seen on notice 108109 (whose text does say Newcastle).
- **Tenders outside the North are rejected, and so are UK-wide contracts and notices that do not say where the work is** (D25, the client's rule). A northern tender that does not state its region, or whose region the LLM misreads, is rejected without review. The LLM now also reads named places (D26), which brought back 106476 (Sheffield College, rejected at first because its notice has no delivery code). In the 9–15 Nov run the shortlist went from 28 before D25 to 9; 6 notices are still rejected as "region not stated", mostly Scottish, Northern Irish or overseas buyers.
- **Borderline service classifications can flip between reads.** 107673 (minor works, joinery and redecoration, Merseyside) was "construction" in one extraction and "building maintenance" in the next, after a prompt change that did not touch services, so it moved from rejected to shortlisted at 0.95. The cache keeps a week's results repeatable, but any re-read can change them. Ties at 0.95 can also name a different best lot after a re-read (107285, 106942).
- **Region no longer separates eligible lots.** Every eligible lot scores 1 on region, so a lot whose main service the company does not offer reaches 0.65 when everything else is perfect, and exactly the 0.60 threshold when mobilisation is not stated (107285's scaffolding, water mains and pest-control lots). To be tuned in slice 4.
- **A lot whose main service the company does not offer can still be shortlisted.** Service fit is only 35% of the score: notice 106652 (community equipment decontamination, "other") reached exactly 0.60.
- **Specialist M&E counts as building maintenance.** Lifts, fire-safety systems, boiler controls and heating frameworks were all classed as "planned and reactive building maintenance" and score 1.0 on service. The profile's service labels are too broad to separate them, and the client does not do this work (D27). The LLM also picks a different lot type between reads (106942's general building lots were classed as construction on the second read).
- **Mobilisation is almost never stated,** so it scores 0.5 nearly everywhere and caps a lot's score at 0.95.
- **Staff checks and licences never gate** (DBS, CSCS, SIA licences, waste-carrier registration, Gas Safe, insurance; D22). A notice that truly depends on one the company cannot get is still shortlisted.
- **Red flags (TUPE, short deadline, closed framework call-off) are extracted but not scored.** A call-off only open to existing framework suppliers can still be shortlisted; the flag is there for the bid team to see.
- **Lots the model leaves out are not scored.** If the extraction covers none of a notice's lots, the notice goes to "needs review"; if it covers some, the missing ones are ignored.
- **A provider error stops the run** (bad key, network). Extractions done so far are cached, so running again continues where it stopped.
- **The budget stops early rather than late.** Each call is checked against its worst case (full output allowance), so a run can stop with up to one call's maximum unspent.
- **Rationales are not checked in code.** The prompt gets only scored fields (D23) and the real week's 28 rationales matched them, but nothing verifies a number or place in the text. They also mostly restate the score breakdown.
- **Rationales are not cached.** Every run pays for them again (about $0.03 for a week).
- **Scottish notices link to the Public Contracts Scotland API,** not a page a person can read, because that is the URL the source data gives.
- **The report shows the notice's total value,** not the best lot's; the lot's value is in the score breakdown.
- **Scoring numbers are first guesses** (unknown = 0.5, over £5m = 0.3, minor excluded service −0.25, threshold 0.6) until the eval in slice 4 tunes them.

## Next steps (if this were a paid engagement)
<!-- What you would do next, in order, and why. Write this yourself. -->
1. Label 100+ notices from weeks the threshold never saw, and report results on that held-out set.
2. Time a bid manager reviewing one weekly report, and record shortlist size and confusing entries.
3. Require supporting quotes for every extracted field, not only the gate fields.
4. Apply the region gate in the pre-filter for notices with delivery addresses, so out-of-region notices cost no LLM call.
5. Incumbent lookup from award notices, and an MCP server (`search_tenders`, `get_tender`, `shortlist`).

## How AI was used
Built with Claude Code and reviewed by Codex; see [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).
