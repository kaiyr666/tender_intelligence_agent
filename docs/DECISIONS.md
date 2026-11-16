# Decisions

<!-- One entry per real choice. Newest at the bottom. Keep each entry short. -->

## D1: Overall approach
- **Chose:** a fixed workflow with two LLM steps: fetch → code pre-filter → LLM extract → code score → LLM rationale → report.
- **Alternatives:** plain software (keywords and CPV only); retrieval (embed notices and match against the profile); an agent that browses and decides.
- **Why:** the task is a bounded sequence over one source, with business rules that must be deterministic and testable, and nothing that needs a model to choose its own tools. Only the free text needs a model. Plain software misses tenders worded in unexpected ways, which is the client's main pain. Retrieval and an agent could both be made to work with a coded rubric, but they add build time and run-to-run variation without solving a problem this proof of concept has.
- **Revisit if:** pre-filter recall in the eval is low. Retrieval or a cheap LLM relevance check could then find candidates the CPV codes miss, with scoring still in code.

## D2: Model and provider
- **Chose:** Anthropic Claude Sonnet (`claude-sonnet-5-5`, the default in `config.py`) through `src/app/llm.py`.
- **Alternatives:** Haiku (cheaper); OpenAI (already supported by `llm.py`).
- **Why:** the brief specifies Claude Sonnet. Extraction from long, messy notices benefits from the stronger model, and the pre-filter keeps the call count low enough to fit the $5 cap.
- **Revisit if:** the slice 2 cost log projects more than $5 for a run plus eval. Then try Haiku for extraction and compare field accuracy.

## D3: Profile and weights in TOML
- **Chose:** `config/profile.toml`, read with the standard library's `tomllib`.
- **Alternatives:** YAML (needs PyYAML); JSON (no comments).
- **Why:** no new dependency, and it allows comments, so a consultant can retune the profile for another client.
- **Revisit if:** config needs features TOML handles poorly (not expected).

## D4: HTTP with the standard library
- **Chose:** `urllib.request` for the Find a Tender API.
- **Alternatives:** `httpx` / `requests` as a direct dependency.
- **Why:** it makes a few GET requests with paging and `Retry-After`, which the standard library does in a few lines without a new dependency.
- **Revisit if:** we need async or connection pooling for much larger date ranges.

## D5: One row per notice, scored on its best eligible lot
- **Chose:** extract, gate and score every lot on all criteria (services, region, value, accreditations, mobilisation), with notice-wide requirements applied to each. Output one row per notice that names the best eligible lot.
- **Alternatives:** one row per lot; taking only region and value from the lot (the first draft).
- **Why:** the team reads by notice, and per-lot rows multiply review time. Scoring only part of a lot could pair a northern cleaning lot with another lot's services or requirements (both Codex reviews, P1).
- **Revisit if:** the team wants to track bids per lot.

## D6: Hard gates versus penalties
- **Chose:** gates for value < £100k, an excluded service as the main scope, and a missing mandatory accreditation. Value over £5m and out of region are penalties.
- **Alternatives:** gate on region and on value over £5m as well (the brief reads that way).
- **Why:** the client's decision. Over £5m can be bid with a partner, and region is often unclear in the text, so a penalty protects recall.
- **Revisit if:** the eval shows out-of-region notices crowding the shortlist (precision < 60%).

## D7: Shortlist cut by score threshold
- **Chose:** a minimum score in config, tuned on the eval set to reach recall ≥ 80%.
- **Alternatives:** a fixed top N.
- **Why:** weekly volume varies, and a top N either drops good tenders or pads the list.
- **Revisit if:** busy weeks give shortlists too long to review in 15 minutes.

## D8: LLM-driven gates need a supporting quote
- **Chose:** the excluded-service and missing-accreditation gates only reject when the extraction's supporting quote is found in the notice text. Otherwise the notice goes to "needs review".
- **Alternatives:** trust the validated extraction; require quotes for every field.
- **Why:** a valid-looking extraction can still invent a mandatory accreditation, and a wrong hard reject is a missed tender. Quotes for every field cost more tokens and time than the time box allows.
- **Revisit if:** the eval shows wrong values in fields that only affect the score.

## D9: Evaluation on one small set, reported as preliminary
- **Chose:** about 30 cases covering the whole pipeline (pre-filter rejects included), a frozen evaluation date, TP/FP/FN counts, and the threshold tuned on the same set.
- **Alternatives:** separate calibration and held-out sets (Codex's recommendation).
- **Why:** splitting 30 cases leaves too few on either side to say anything, and labelling more does not fit the time box. The numbers are stated as preliminary.
- **Revisit if:** this goes beyond a proof of concept. Then label 100+ notices from weeks the threshold never saw.

## D10: Cost is controlled before calls, not logged after
- **Chose:** record token usage in `llm.py`, cache extractions by notice ID and release date, cap input length, and stop LLM calls before a configured budget is exceeded.
- **Alternatives:** a cost log read after the run.
- **Why:** a log only shows overspending once it has happened, and the weekly volume from the API is not yet known.
- **Revisit if:** slice 1 shows the volume is small enough that the cap never matters.

## D11: Fetch all stages and filter tags in code
- **Chose:** request every stage and keep releases tagged `tender` / `tenderUpdate`, `planning` / `planningUpdate` and `tenderCancellation`, taking the latest release per `ocid`.
- **Alternatives:** the API's `stages=tender` parameter.
- **Why:** for 9–15 Nov 2026, `stages=tender` returned 41 releases on one page, while the unfiltered feed had 366 `tender` and 141 `tenderUpdate` releases. Fetching everything costs about 3 minutes a week.
- **Revisit if:** the API's stage filter is fixed (compare counts for one week).

## D12: CPV match by hierarchy, plus a short list of exact broad codes
- **Chose:** a notice code matches when it equals a profile code or sits under it (the division, the first two digits, always counts). Two broad parent codes, 50000000 and 90900000, match only exactly. Notices with no CPV code are kept.
- **Alternatives:** match notice parent codes against any profile code below them; or add 50000000 as a full prefix.
- **Why:** measured on the real week. Exact codes alone missed "Window and High Level Cleaning" (90900000) and "Reactive and Planned Maintenance" (50000000). Matching every parent code kept 48 extra notices, of which about 3 were relevant (most were 45000000 construction). A full 50000000 prefix added vehicle, aircraft and machinery repair. The chosen rule kept 63 of 463.
- **Revisit if:** the eval's pre-filter recall is low. Known near misses are fire-system and automatic-door maintenance (50413100, 50330000), which the profile does not cover.

## D13: Deadline falls back to the expression-of-interest date
- **Chose:** use `tender.tenderPeriod.endDate`, or `tender.expressionOfInterestDeadline` when there is no tender period.
- **Alternatives:** treat the deadline as unknown.
- **Why:** some procedures publish only an expression-of-interest deadline, and that is the first date the bid team must meet. The `test-writer` agent spotted it in the fixture.
- **Revisit if:** the team wants both dates shown separately.

## D14: Store reduced notices only, never raw API data
- **Chose:** `data/raw/notices_<from>_<to>.json` holds Notice objects: no parties except the buyer's name, and emails and phones masked in free text. The eval set is 32 such notices in `evals/notices.json` (23 kept by the pre-filter, 9 dropped near misses).
- **Alternatives:** cache raw releases and reduce them on read.
- **Why:** raw releases carry named contacts, emails and phone numbers (17 notices in one week also had emails inside descriptions). Not storing them is simpler than securing them.
- **Revisit if:** a later step needs a field the Notice drops; it then has to be added to the model and re-fetched.

<!--
Template:
## Dn: <decision>
- **Chose:**
- **Alternatives:**
- **Why:**
- **Revisit if:**
-->
