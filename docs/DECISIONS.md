# Decisions

<!-- One entry per real choice. Newest at the bottom. Keep each entry short. -->

## D1: Overall approach
- **Chose:** a fixed workflow with two LLM steps: fetch → code pre-filter → LLM extract → code score → LLM rationale → report.
- **Alternatives:** plain software (keywords and CPV only); retrieval (embed notices and match against the profile); an agent that browses and decides.
- **Why:** the hard parts are exact (CPV, value, dates, rubric), so they stay in code and can be tested. Only the free text needs a model. Plain software misses tenders worded in unexpected ways, which is the client's main pain. Retrieval gives a similarity number, not an explainable score. An agent costs more, behaves differently on each run, and would let the LLM decide the score, which the brief forbids.
- **Revisit if:** the eval shows the CPV pre-filter drops good tenders, which would mean a cheap LLM relevance check is needed before the filter.

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

## D5: One row per notice, scored on its best lot
- **Chose:** score each lot's region and value, keep the best-fitting lot, and output one row per notice that names that lot.
- **Alternatives:** one row per lot.
- **Why:** the team reads by notice, and per-lot rows multiply review time on large frameworks. Chosen by the client.
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

<!--
Template:
## Dn: <decision>
- **Chose:**
- **Alternatives:**
- **Why:**
- **Revisit if:**
-->
