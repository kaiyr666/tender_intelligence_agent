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

## Next steps (if this were a paid engagement)
<!-- What you would do next, in order, and why. Write this yourself. -->
1. Label 100+ notices from weeks the threshold never saw, and report results on that held-out set.
2. Time a bid manager reviewing one weekly report, and record shortlist size and confusing entries.
3. Require supporting quotes for every extracted field, not only the gate fields.
4. Incumbent lookup from award notices, and an MCP server (`search_tenders`, `get_tender`, `shortlist`).

## How AI was used
Built with Claude Code and reviewed by Codex; see [docs/AI_WORKFLOW.md](docs/AI_WORKFLOW.md).
