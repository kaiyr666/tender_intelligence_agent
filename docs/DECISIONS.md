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

<!--
Template:
## Dn: <decision>
- **Chose:**
- **Alternatives:**
- **Why:**
- **Revisit if:**
-->
