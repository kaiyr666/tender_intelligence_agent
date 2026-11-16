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
- **Only the two LLM-driven gates are checked against the notice text.** Other extracted fields (region, contract length, mobilisation) are validated for shape, not for truth.
- **The 15-minute review target is not measured.** No bid manager has timed a real review.
- **The CPV pre-filter misses relevant work coded outside the profile.** For example, fire-system servicing (50413100) and automatic-door maintenance (50330000) are dropped before the LLM sees them.
- **Phone masking over-masks.** Any 10–11 digit reference starting with 0 is masked as if it were a phone number.
- **Values in other currencies are treated as unknown.** One UK lot that week was labelled AED in the source data.
- **A week's fetch takes about 3 minutes,** because the API's stage filter is unreliable and every stage has to be fetched (D11).
- **Accreditation names are matched loosely.** A requirement for "Cyber Essentials Plus" counts as held because the company holds "Cyber Essentials". "X or equivalent" with only X named is treated as X, so "CHAS or equivalent" is rejected even though SafeContractor would qualify. Groups that name the alternatives ("CHAS, SafeContractor or Constructionline") are handled.
- **Staff checks and licences never gate** (DBS, CSCS, SIA licences, waste-carrier registration, Gas Safe, insurance; D22). A notice that truly depends on one the company cannot get is still shortlisted.
- **Red flags (TUPE, short deadline, closed framework call-off) are extracted but not scored.** A call-off only open to existing framework suppliers can still be shortlisted; the flag is there for the bid team to see.
- **Lots the model leaves out are not scored.** If the extraction covers none of a notice's lots, the notice goes to "needs review"; if it covers some, the missing ones are ignored.
- **A provider error stops the run** (bad key, network). Extractions done so far are cached, so running again continues where it stopped.
- **The budget stops early rather than late.** Each call is checked against its worst case (full output allowance), so a run can stop with up to one call's maximum unspent.
- **Scoring numbers are first guesses** (unknown = 0.5, over £5m = 0.3, minor excluded service −0.25, threshold 0.6) until the eval in slice 4 tunes them.

## Next steps (if this were a paid engagement)
<!-- What you would do next, in order, and why. Write this yourself. -->
1. Label 100+ notices from weeks the threshold never saw, and report results on that held-out set.
2. Time a bid manager reviewing one weekly report, and record shortlist size and confusing entries.
3. Require supporting quotes for every extracted field, not only the gate fields.
4. Incumbent lookup from award notices, and an MCP server (`search_tenders`, `get_tender`, `shortlist`).

## How AI was used
Built with Claude Code and reviewed by Codex; see [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).
