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
- **The eval numbers are preliminary.** 42 hand-picked cases, all now used for fixes: the 32 the profile and threshold were tuned on, and the 10 added afterwards, which scored 50% recall until the pre-filter was fixed on them (D32). Both now score 100% precision and recall, which says little about unseen weeks. One unseen week (26 Oct–1 Nov) was screened blind by the human (D33): after review the tool found 4 of 5 bids and 4 of its 5 shortlisted notices were bids, but 5 bids is too few for a rate. Results in `docs/EVAL.md`.
- **Every construction-coded notice is read by the LLM** (D32), because buyers code repairs and maintenance as construction. That doubles a week's LLM reads (61 to 122 notices in 9–15 Nov, $0.29), and keeping capital projects off the shortlist now rests on the LLM naming construction as the main service with a quote. In that week all the new notices were rejected. In the blind week it happened once: structural repairs to Blackpool Tower (engineering and structural steel codes) were read as building maintenance and shortlisted at 0.95.
- **Other CPV codes outside the profile are still dropped unread.** Fire-system and automatic-door servicing (50413100, 50330000) is dropped, which suits the client now that specialist M&E is out of scope (D27); a relevant notice coded only with an unrelated code is missed. In the blind week that was supply and installation of bin and scooter stores at Newcastle housing blocks (44000000), which the human judged a borderline bid.
- **A value of £0 is read as "not stated"** (D32), so it scores the neutral 0.5 rather than being dropped. A real contract of £0 (a concession paid by users) is treated the same way.
- **The committed eval extractions go stale on any prompt or profile change.** The offline eval and its test then fail until `uv run python -m evals.run --live` re-reads the 42 notices (about $0.20). This is deliberate: an eval silently scored on old extractions would mislead.
- **Personal names in free text are not removed.** Contact details in `parties[]` are dropped and emails and phone numbers in descriptions are masked, but a name written into a description stays.
- **Only the excluded-service and accreditation gates are checked against the notice text.** The region gate trusts the LLM's reading when a notice has no delivery address (D25), and other extracted fields (contract length, mobilisation) are validated for shape, not for truth.
- **The 15-minute review target is not measured.** No bid manager has timed a review of the report. As a baseline, the human's blind manual screen of 137 already narrowed notices took about 1 hour, and reviewing the tool's 10 disagreements took 15 minutes.
- **Phone masking over-masks.** Any 10–11 digit reference starting with 0 is masked as if it were a phone number.
- **Values in other currencies are treated as unknown.** One UK lot that week was labelled AED in the source data.
- **A week's fetch takes about 3 minutes,** because the API's stage filter is unreliable and every stage has to be fetched (D11).
- **Accreditation names are matched loosely.** A requirement for "Cyber Essentials Plus" counts as held because the company holds "Cyber Essentials". "X or equivalent" with only X named is treated as X, so "CHAS or equivalent" is rejected even though SafeContractor would qualify. Groups that name the alternatives ("CHAS, SafeContractor or Constructionline") are handled.
- **A delivery-address list that covers most of England counts as in region.** A lot passes the region gate when any delivery code is in the North, so a notice listing every English region passes like a northern one, although UK-wide contracts are meant to be rejected. Seen on notice 108109 (whose text does say Newcastle). In the blind week the human would bid such a lot (EEM fire doors, national coverage, 100829), so this may be what the client wants; the rule needs confirming.
- **Tenders outside the North are rejected, and so are UK-wide contracts and notices that do not say where the work is** (D25, the client's rule). A northern tender that does not state its region, or whose region the LLM misreads, is rejected without review. The LLM now also reads named places (D26), which brought back 106476 (Sheffield College, rejected at first because its notice has no delivery code). In the 9–15 Nov run the shortlist went from 28 before D25 to 9, and to 8 after slice 4's profile changes (D28–D30), all of them labelled bids in the eval; 6 notices are still rejected as "region not stated", mostly Scottish, Northern Irish or overseas buyers.
- **Borderline service classifications can flip between reads.** 107673 (minor works, joinery and redecoration, Merseyside) was "construction" in one extraction and "building maintenance" in the next. Each service now has written includes and excludes (D28), and on the eval re-read every bid lot was classed as the client would; the remaining service misses are out-of-scope notices (a Northern Ireland construction framework read as building maintenance, a food hall as "other" rather than catering), where another gate decides. The cache keeps a week's results repeatable, but any re-read can change them. Ties at 0.95 can also name a different best lot after a re-read.
- **Region no longer separates eligible lots.** Every eligible lot scores 1 on region, so a lot whose main service the company does not offer can reach 0.65. The threshold of 0.70 (D30) keeps such lots off the shortlist, but a bid lot with unknown value, unknown mobilisation and a short deadline can also fall under 0.70.
- **Specialist M&E is excluded by a label the LLM must apply.** HVAC, gas, heating, lifts and fire systems are an excluded service (D28) and M&E-only CPV codes no longer pass the pre-filter (D29), but a mixed lot is gated only when the LLM names M&E as its main service with a quote. Fire doors count as joinery, which the client does (check-set case 105640), so the line between them and fire systems rests on the LLM's reading.
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
- **Most scoring numbers are still first guesses** (unknown = 0.5, over £5m = 0.3, minor excluded service −0.25, the weights). Only the threshold (0.70) was set on the eval, and the eval is too small to tune the rest.

## Next steps (if this were a paid engagement)
<!-- What you would do next, in order, and why. Write this yourself. -->
1. Label 100+ notices from weeks the threshold never saw, and report results on that held-out set.
2. Time a bid manager reviewing one weekly report, and record shortlist size and confusing entries.
3. Require supporting quotes for every extracted field, not only the gate fields.
4. Apply the region gate in the pre-filter for notices with delivery addresses, so out-of-region notices cost no LLM call.
5. Incumbent lookup from award notices, and an MCP server (`search_tenders`, `get_tender`, `shortlist`).

## How AI was used
Built with Claude Code and reviewed by Codex; see [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).
