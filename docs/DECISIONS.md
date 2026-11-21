# Decisions

<!-- One entry per real choice. Newest at the bottom. Keep each entry short. -->

## D1: Overall approach
- **Chose:** a fixed workflow with two LLM steps: fetch → code pre-filter → LLM extract → code score → LLM rationale → report.
- **Alternatives:** plain software (keywords and CPV only); retrieval (embed notices and match against the profile); an agent that browses and decides.
- **Why:** the task is a bounded sequence over one source, with business rules that must be deterministic and testable, and nothing that needs a model to choose its own tools. Only the free text needs a model. Plain software misses tenders worded in unexpected ways, which is the client's main pain. Retrieval and an agent could both be made to work with a coded rubric, but they add build time and run-to-run variation without solving a problem this proof of concept has.
- **Revisit if:** pre-filter recall in the eval is low. Retrieval or a cheap LLM relevance check could then find candidates the CPV codes miss, with scoring still in code.

## D2: Model and provider (superseded by D15)
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

## D6: Hard gates versus penalties (region part superseded by D25)
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

## D15: OpenAI instead of Claude Sonnet
- **Chose:** the OpenAI provider in `llm.py`, with the model set by `LLM_PROVIDER=openai` and `LLM_MODEL` in `.env`.
- **Alternatives:** Claude Sonnet as in D2; it still works by changing `LLM_PROVIDER`.
- **Why:** the human's decision in slice 2: the API key available is an OpenAI one. The OpenAI call uses `max_completion_tokens`, which newer OpenAI models require instead of `max_tokens`, and JSON mode.
- **Revisit if:** extraction accuracy in the eval is weak; then compare with Claude Sonnet on the same cases.
- **Measured (slice 2):** one extraction with `gpt-6.1-terra` ($1.00 / $5.00 per million tokens, OpenAI pricing page) on a single-lot notice took 1,953 input and 622 output tokens: $0.005 in 14 seconds, valid on the first attempt. About 60 notices a week is roughly $0.30 a run, and the eval about $0.20, well under the $5 cap. The $2.50 default budget is a safety net that a normal week should not reach (D10).

## D16: Prices come from config, and an unknown price stops the run
- **Chose:** each provider carries its price per million tokens. Prices are known in `config.py` for Claude Sonnet only; any other model needs `LLM_INPUT_USD_PER_MTOK` and `LLM_OUTPUT_USD_PER_MTOK` in `.env`, or the run refuses to start. The budget is `LLM_BUDGET_USD` (default $2.50).
- **Alternatives:** a price table in code for OpenAI models; running without a budget when the price is unknown.
- **Why:** prices change and differ per model, so a table written from memory would be wrong without anyone noticing. Without a price the budget cannot work, and failing closed is safer than spending blind.
- **Revisit if:** the provider's API starts returning cost per call.

## D17: Budget checked against a worst-case estimate before every attempt
- **Chose:** before each attempt (retries included), `llm.py` estimates input tokens at 3 characters per token and output at the full allowance of 8,000 tokens, and refuses the call if that could pass the budget. Actual tokens from the response are what is added up.
- **Alternatives:** checking actual spend after each call; counting tokens exactly with a tokenizer.
- **Why:** checking afterwards can overshoot by one call. A worst-case estimate never overshoots and needs no tokenizer dependency. The cost is stopping a little early, by at most one call's maximum.
- **Revisit if:** runs often stop with much of the budget unspent.

## D18: One extraction call per notice, with notice-wide requirements kept apart
- **Chose:** one call returns every lot, plus the notice-wide mandatory and preferred accreditations and red flags; code adds the notice-wide requirements to each lot. The LLM classifies services into the profile's labels (or "other: ..."), and code matches labels.
- **Alternatives:** one call per lot; asking the model to repeat notice-wide requirements in every lot; free-text services matched by keyword.
- **Why:** one call per notice is cheaper and gives the model the whole notice. Keeping notice-wide requirements apart means a requirement cannot be forgotten on one lot. Using the profile's own labels keeps the service match exact and in code.
- **Revisit if:** notices with many lots hit the output limit (they then go to "needs review").

## D19: Scoring shapes: unknown is 0.5, shortfalls scale down
- **Chose:** a criterion the notice does not state scores 0.5. Mobilisation and deadline score weeks or days available divided by what the profile needs, capped at 1. Value over £5m scores 0.3. A minor excluded service costs 0.25 on service fit. The accreditations criterion scores the share of preferred accreditations held (mandatory ones are gates). Accreditations are matched by name after removing case and punctuation ("ISO 9001:2015" counts as ISO 9001).
- **Alternatives:** unknown scores 0 (penalises vague notices, which are common); step functions.
- **Why:** a vague notice is not a bad one, and recall matters more than precision for the client. Linear shortfalls are easy to explain to the bid team. The numbers are first guesses for the eval to test.
- **Revisit if:** the eval shows vague notices crowding the shortlist.

## D20: The extraction cache key includes the prompt input
- **Chose:** `data/cache/extractions/<notice id>_<release date>_<hash>.json`. The hash covers the prompt file, the model and the filled-in prompt (notice text and profile labels).
- **Alternatives:** notice ID and release date only (the spec's wording).
- **Why:** with only the ID and date, editing the prompt or the profile while tuning would silently reuse old extractions and make eval numbers meaningless.
- **Revisit if:** never needed; old files can simply be deleted.

## D21: API failures stop the run; bad output goes to review
- **Chose:** output that fails validation twice sends that notice to "needs review" and the run continues. A provider error (bad key, network, rate limit after the SDK's retries) stops the run with a message; extractions so far stay cached, so a rerun continues where it stopped.
- **Alternatives:** marking every notice as "needs review" when the API fails.
- **Why:** a bad key would otherwise produce a report of 60 "needs review" notices that looks like a result. Stopping is clearer, and the cache makes rerunning cheap.
- **Revisit if:** transient API errors stop weekly runs often.

## D22: Only organisation-level certifications can be a mandatory-accreditation gate
- **Chose:** the extract prompt lists as mandatory only audited, organisation-level certificates and scheme memberships (ISO standards, Cyber Essentials, SSIP schemes, SIA Approved Contractor, NICEIC, BAFE). Staff checks and cards (DBS, CSCS, SIA licences), statutory registrations and licences (waste carrier, Gas Safe), insurance and policies are not extracted, so they never gate. "One of" groups are recorded as one entry, and they count as held when the company holds any scheme in the group.
- **Alternatives:** (a) gate on every stated requirement, staff checks included; (b) add DBS, CSCS and a waste-carrier licence to the profile's `held` list.
- **Why:** (a) rejects in-region FM frameworks the company would bid for. Draft eval label 106942 (North East Lincolnshire FM repairs) failed every lot on CSCS, DBS and waste-carrier wording. Yet a security and cleaning firm DBS-checks staff as a matter of course, CSCS cards are per worker, and a waste-carrier registration is quick to get, so none of these is a reason to skip a tender. A wrong reject is a missed tender, the client's main pain, while a wrong pass costs one notice the bid team opens. (b) would write facts about the client into config that nobody has confirmed. The cost: a notice that truly hinges on a licence the company cannot get is shortlisted, and the bid team sees it when they open it.
- **Revisit if:** the client confirms which staff vetting and licences they hold, or the eval shows shortlisted notices that fail on such a requirement.

## D23: The rationale sees scored fields only, and never blocks the report
- **Chose:** the rationale prompt gets the best lot's criterion scores and reasons, its extracted labels and numbers, accreditation names and red-flag kinds. It never gets the title, buyer, description or quotes. A rationale that fails (invalid output, budget, provider error) is replaced by "Rationale not written (...); see the score breakdown", and after a budget or provider error no further rationale calls are made.
- **Alternatives:** pass the notice text for a richer rationale; stop the run on a provider error as extraction does (D21).
- **Why:** the spec says the rationale uses extracted fields only, so it cannot claim anything scoring did not see, and keeping notice text out also keeps third-party text away from this prompt. Unlike a failed extraction, a missing rationale changes no outcome: the score breakdown is printed next to it, so the report is still correct and worth writing.
- **Revisit if:** the bid team finds the rationales only repeat the breakdown. Then add short extracted quotes, which are checked against the notice, to the facts.

## D24: The CSV holds every assessed notice, with its outcome
- **Chose:** `shortlist.csv` has one row per notice that reached extraction (all four report groups), with `outcome`, rank for shortlisted rows, scores per criterion, reason and rationale. Text cells that start with `=`, `+`, `-`, `@` or a tab are prefixed with `'`, and the file is UTF-8 with a byte-order mark.
- **Alternatives:** shortlisted rows only, as the file name suggests.
- **Why:** the spec calls the CSV "the same data" as the report, and the team needs the needs-review and rejected rows to check the tool's calls; filtering on `outcome` in a spreadsheet is one click. Titles come from third parties, so a title starting with `=` must not run as a formula in Excel, and Excel needs the byte-order mark to read "£".
- **Revisit if:** the team's tracker import wants shortlisted rows only.

## D25: Region is a hard gate, including UK-wide and not stated
- **Chose:** a lot is rejected when its delivery region is outside UKC, UKD and UKE, is UK-wide with no regional lot, or is not stated. Region comes from delivery-address codes when the notice has them, and from the LLM's reading of the text otherwise; both reject, with no quote check.
- **Alternatives:** (a) keep region a penalty (D6) and raise its weight in slice 4; (b) Claude's recommendation: gate only out-of-region delivery addresses, keep UK-wide and unstated regions as penalties, and send regions read from the text to "needs review".
- **Why:** the human's decision for the client after the first real week, where 21 of 28 shortlisted notices were outside the North or had no region. The brief says the client considers national contracts only when they are split into regional lots. A hard rule is clearer to the bid team than a weight, and re-scoring needs no new LLM calls.
- **Cost:** a northern tender whose notice does not say where the work is, or whose region the LLM misreads, is rejected without review, which departs from D8 for this gate. Every eligible lot now scores 1 on region, so the 0.20 region weight no longer separates eligible lots and lowers the bar for the other five criteria: a lot whose main service the company does not offer reaches 0.65 when everything else is perfect.
- **Revisit if:** the eval finds bid-labelled northern notices rejected on region, especially "not stated". Slice 4 should retune the region weight and the threshold.

## D26: The LLM maps named places to a region
- **Chose:** the extract prompt tells the model to give the NUTS 1 code for a named town, city, county or site where the work is done ("across the Sheffield College estate" → UKE), and to leave the region empty only when no place is named. Delivery-address codes still win when present (code).
- **Alternatives:** a place-name lookup table in code; leaving "not stated" as it was.
- **Why:** since D25 an empty region is a hard reject, and Sheffield College's HVAC servicing (106476, Yorkshire) was rejected only because its notice had no delivery code. Placing a named town in a NUTS 1 region is reading, which is the LLM's job; a lookup table would need a gazetteer of every UK place and would still miss "the Trust's sites".
- **Cost:** the region the gate relies on is still the LLM's reading, with no quote check (D25). Changing the prompt invalidated the cache, so the week's 59 notices were read again.
- **Revisit if:** the eval shows regions guessed from the buyer's address rather than the place of work.

## D27: The client's answers on service scope
- **Chose:** (1) minor works, joinery and redecoration count as building maintenance; (2) the company does grounds maintenance; (3) specialist cleaning such as decontaminating community care equipment is not its work; (4) lots over £5m stay a score penalty, not a reject; (5) specialist trade lots in maintenance frameworks (scaffolding, drainage, glazing, windows, fencing and similar) are bid for, as building maintenance. This was first recorded as "not bid for"; the human corrected it. (6) The company does not do specialist M&E: HVAC, gas, lifts and fire systems. The draft eval labels follow these answers.
- **Alternatives:** keep the drafting agent's guesses (it labelled 107673 and 107285 low confidence, and 106185 no-bid).
- **Why:** the human's answers for the client, needed so the eval measures the tool against the client's judgement rather than an AI's.
- **Cost:** (2) widens the brief's service list (cleaning, security, building maintenance). The profile does not yet match (2) and (6): grounds maintenance is not an offered service or CPV code, and specialist M&E is classed as building maintenance (Sheffield College HVAC, 106476, is shortlisted at 0.95). Slice 4 updates `config/profile.toml` before tuning. (5) already matches: specialist trades are classed as building maintenance, so 107285 is shortlisted on its drainage lot.
- **Revisit if:** the bid team disagrees with any of these on a real weekly report.

<!--
Template:
## Dn: <decision>
- **Chose:**
- **Alternatives:**
- **Why:**
- **Revisit if:**
-->
