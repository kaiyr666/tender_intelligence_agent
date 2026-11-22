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
- **Clarified (22 Nov):** a national-coverage lot, whose delivery codes list the North among every other region, counts as UK-wide and is rejected; the human confirmed this for the client after the blind screen (100829). The region gate now rejects such lots (D34).

## D26: The LLM maps named places to a region
- **Chose:** the extract prompt tells the model to give the NUTS 1 code for a named town, city, county or site where the work is done ("across the Sheffield College estate" → UKE), and to leave the region empty only when no place is named. Delivery-address codes still win when present (code).
- **Alternatives:** a place-name lookup table in code; leaving "not stated" as it was.
- **Why:** since D25 an empty region is a hard reject, and Sheffield College's HVAC servicing (106476, Yorkshire) was rejected only because its notice had no delivery code. Placing a named town in a NUTS 1 region is reading, which is the LLM's job; a lookup table would need a gazetteer of every UK place and would still miss "the Trust's sites".
- **Cost:** the region the gate relies on is still the LLM's reading, with no quote check (D25). Changing the prompt invalidated the cache, so the week's 59 notices were read again.
- **Revisit if:** the eval shows regions guessed from the buyer's address rather than the place of work.

## D27: The client's answers on service scope
- **Chose:** (1) minor works, joinery and redecoration count as building maintenance; (2) the company does grounds maintenance; (3) specialist cleaning such as decontaminating community care equipment is not its work; (4) lots over £5m stay a score penalty, not a reject; (5) specialist trade lots in maintenance frameworks (scaffolding, drainage, glazing, windows, fencing and similar) are bid for, as building maintenance. This was first recorded as "not bid for"; the human corrected it. (6) The company does not do specialist M&E: HVAC, gas, lifts and fire systems. (7) It does general electrical maintenance; lots that require NICEIC are still rejected, because the company does not hold it. The draft eval labels follow these answers.
- **Alternatives:** keep the drafting agent's guesses (it labelled 107673 and 107285 low confidence, and 106185 no-bid).
- **Why:** the human's answers for the client, needed so the eval measures the tool against the client's judgement rather than an AI's.
- **Cost:** (2) widens the brief's service list (cleaning, security, building maintenance). The profile does not yet match (2) and (6): grounds maintenance is not an offered service or CPV code, and specialist M&E is classed as building maintenance (Sheffield College HVAC, 106476, is shortlisted at 0.95). Slice 4 updates `config/profile.toml` before tuning. (5) already matches: specialist trades are classed as building maintenance, so 107285 is shortlisted on its drainage lot.
- **Revisit if:** the bid team disagrees with any of these on a real weekly report.

## D28: Service definitions live in the profile, next to each label
- **Chose:** each service in `config/profile.toml` is a table with `name`, `includes` and `excludes`; the extract prompt lists them as "label. Includes: ...; Not: ... (other label)". Grounds maintenance is an offered service; specialist M&E (HVAC, gas, heating, lifts, fire systems) and specialist equipment decontamination are excluded services, so they gate with a quote like construction does.
- **Alternatives:** (a) a separate `[services.definitions]` table keyed by label; (b) definitions written into `prompts/extract.md`.
- **Why:** the label analysis found the same lot classed differently on two reads (107673, 106942 lots 3a and 3b, 108109). Writing down where the boundaries are is the cheapest fix that stays in config, where a consultant can change it for another client (D3). (a) puts a label and its definition in two places that can drift apart; (b) puts client facts into a prompt.
- **Revisit if:** classifications still flip between reads on the eval set; then add one short worked example per borderline case to the prompt.

## D29: CPV list follows the client's scope; 50700000 matches only exactly
- **Chose:** add 77310000 (grounds maintenance and its sub-codes); remove 50710000, 50720000, 50730000 and 50750000 (M&E); move 50700000 to the exact-match list and add 50711000 (electrical installations), because the company does general electrical work.
- **Alternatives:** keep 50700000 as a prefix and let the LLM's excluded-service gate drop M&E; a list of "never" codes.
- **Why:** measured on 9–15 Nov. As a prefix, 50700000 kept 11 notices whose only matching codes were M&E (lifts, heating, HVAC, laundry equipment), each an LLM call that the gate then has to get right; Sheffield College HVAC (106476) was shortlisted at 0.95 that way. As an exact code it still keeps joinery, roofing and minor works coded 50700000 (107545, 106971). A "never" list would drop a mixed framework for one bad lot. Adding 7731 keeps 8 grounds-maintenance notices that week, one a bid in the eval (106185).
- **Revisit if:** a relevant building-maintenance notice coded only with a 507xxxxx M&E code is missed.

## D30: Threshold 0.70 closes the "other service" loophole
- **Chose:** raise `shortlist_threshold` from 0.60 to 0.70.
- **Alternatives:** gate a lot whose main service is "other" (not offered, not excluded).
- **Why:** since region became a gate (D25), a lot with service fit 0 can score at most 0.65 (0.60 with mobilisation unknown, which is nearly always), so any threshold above 0.65 shuts it out with no new rule. On the tuning set the sweep keeps 100% precision and recall from 0.50 to 0.75, so 0.70 sits between the 0.65 ceiling and the lowest-scoring bid. A gate on "other" would reject on an LLM reading with no quote behind it, against D8, and specialist M&E and decontamination now have their own excluded labels (D28), which gate with a quote.
- **Revisit if:** a bid scores between 0.65 and 0.70 (for example an offered service with unknown value, unknown mobilisation and a short deadline), or the weights change.

## D31: The eval runs the real pipeline offline, from committed extractions
- **Chose:** `evals/run.py` pre-filters, extracts (through `assess`, so with the same cache and budget) and scores the labelled notices against a frozen date (Mon 16 Nov 2026, 09:00 UTC). Extractions are committed in `evals/extractions/` with the model name in `model.txt`; by default the eval makes no LLM call and stops if one is missing, and `--live` reads missing notices and removes files no case uses. "Shortlisted" is the positive prediction, so a bid sent to "needs review" or dropped by the pre-filter counts as a miss. Region is compared as the scorer uses it (delivery codes first, at NUTS 1); requirement names ignore filler words ("accreditation") and ISO edition years. The 10 cases added after tuning are kept as a separate "check" set and reported apart.
- **Alternatives:** a harness with its own copy of the pipeline steps; comparing the LLM's region field, which is ignored whenever delivery codes exist; requiring an API key for every eval run.
- **Why:** reusing `assess` means the eval measures the code that ships. Committed extractions make the numbers reproducible from a clean clone and in CI at no cost, and reruns no longer change with each LLM read. The two comparison rules came from the first run: 5 of 6 region "misses" were notices where the scorer correctly used delivery codes, and "SSIP accreditation" against "SSIP" is not an extraction error. Both are definitions of the field, not fixes to pass a case; the remaining misses stay misses.
- **Revisit if:** the eval grows past about 100 cases, when a held-out split from weeks the threshold never saw becomes possible (D9).

## D32: Construction codes reach the LLM; a value of £0 means "not stated"
- **Chose:** `45000000` joins the profile codes, so every construction (45) code passes the pre-filter and the extraction's construction gate (with a quote) and the region gate decide; it covers the former 45259000 and 45453000. A notice or lot value of £0 is read as not stated, in the `Notice` and `Lot` models, so saved notices and eval cases get the same rule. This partly reverses D12, which kept 45 codes out to save LLM calls.
- **Alternatives:** keep 45-coded notices only when the title or description says "repair" or "maintenance"; a cheap LLM relevance check for 45-coded notices (D1); a pre-filter on delivery-address region to cut the extra calls.
- **Why:** the check set lost 3 of 8 bids to construction coding (103529, 104445, 103643) and one to a £0 value (105298). Measured on the fetched weeks: 65 to 82 notices a week are dropped only on 45 codes. Letting them through doubled what the 9–15 Nov run reads (61 to 122 notices, 62 calls, $0.29) and left its shortlist the same 8; every new notice was rejected as construction, M&E or out of region. A keyword list is the brittle wording match the client already suffers from, and it would be fitted to three notices. A relevance check adds a prompt and a step for a cost problem the $5 cap does not have. The region pre-filter is in the README's next steps.
- **Cost:** the check set has now been used for tuning, so its 8 of 8 is not an independent measure; a fresh labelled set is planned next. Precision now leans more on the construction gate: a refurbishment the LLM reads as building maintenance would be shortlisted.
- **Revisit if:** a weekly run nears its budget, or capital projects reach the shortlist.

## D33: The held-out check is a blind screen of one unseen week
- **Chose:** the human marks every open notice of 26 Oct–1 Nov delivered in the North, UK-wide by lot or with no stated region (137, any CPV code), from notice facts only, before the tool reads the week; then reviews every maybe and every disagreement against the full notice and groups it (tool error, missing rule, changed mark, borderline). Results are reported blind and after review.
- **Alternatives:** label two fresh weeks in full (1 to 2 hours); two AI labellers (Claude and GPT) with the human resolving disagreements; ship with the tuned figures only.
- **Why:** every eval case had been used for fixes, and the client's question is whether the tool picks what its bid team would. A blind human screen answers that directly, covers the pre-filter, and fits the deadline. AI labels test rule-following, not the client's intent, and GPT shares a model family with the extractor. Full labelling spends most of its time on obvious no-bids. Locking the marks before the run keeps them from being anchored on the tool; the review is anchored, so both readings are kept.
- **Cost:** one week gives few bids (5 after review), so the result is counts, not rates. The review changed two blanks to bids after seeing the tool's answer.
- **Revisit if:** the client can run a shadow pilot (the tool beside the manual screen for 3 to 4 weeks), which replaces this with real decisions.

## D34: A lot is in region only when all its regions are in the North
- **Chose:** the region gate passes a lot only when every delivery code, or every region read from the text when there are no codes, is in UKC, UKD or UKE. A lot that also covers any other region is rejected with the reason "also covers regions outside the North". The human chose this for the client on 22 Nov.
- **Alternatives:** (a) when a lot's codes cover 6 or more of the 12 UK regions, treat them as "England" and use the region read from the text, rejecting only if that too covers 6 or more (Claude's recommendation); (b) reject a lot whose codes cover 6 or more regions.
- **Why:** after the blind screen the client confirmed that national-coverage lots are rejected (D25 clarified), and the old rule passed any lot with one northern code, which shortlisted EEM's national fire doors lot (100829). The chosen rule is the simplest to state and check.
- **Cost:** buyers often list all 9 English regions for a local contract. 108109 (Newcastle window cleaning, a labelled bid whose text says Newcastle) is now rejected, so recall on all 42 cases falls from 16/16 to 15/16 and the 9–15 Nov shortlist from 8 to 7. Lots across a regional border, such as Yorkshire and the East Midlands (103415), are rejected too. Option (a) would have kept 108109 and still rejected 100829. The fix was made on the blind week, which is therefore no longer unseen.
- **Revisit if:** the bid team misses local northern contracts coded "all of England"; then use option (a).

## D35: Deadlines show their time, in UTC
- **Chose:** the report and the CSV show a deadline as `2026-12-15 12:00 UTC`, not the date alone (review 04). A deadline given as a date only shows 23:59.
- **Alternatives:** UK local time (Europe/London); the date alone, as before.
- **Why:** a noon deadline and an end-of-day deadline looked the same, and the bid team plans to the hour. UK time would read better, but on Windows Python's time zones need the `tzdata` package, a new dependency for a label; the API gives times in UTC, which is GMT for half the year.
- **Revisit if:** the bid team misreads summer deadlines by an hour; then add `tzdata` and show UK time.

## D36: A read-only web view and a read-only MCP server join the scope
- **Chose:** two read-only views of a run for the 23 Nov demo: a self-contained HTML page for the bid team, and a local stdio MCP server for an AI assistant (slices 6–9). Neither edits the profile, starts a run, calls the LLM or records bid decisions. The human chose this on 22 Nov: "Web UI" had been out of scope by our own assumption, to protect the 5-hour box, not at anyone else's request.
- **Alternatives:** (a) the HTML page only (4–5 h); (b) the MCP server only (2–3 h), Claude's first recommendation, while it still read the out-of-scope line as a client requirement; (c) a local web app (FastAPI) with a Run button, profile editing and bid/no-bid capture (9–12 h, or 16–22 h with full config editing); (d) Streamlit (4–5 h, a new dependency that is hard to make look polished).
- **Why:** the role being interviewed for asks to "sketch the system from data to UI" and to "wire an API or an MCP server"; the two views show both, over one result. The bid team only enters a date range, so the gap is reading, not input. Profile editing would shift every result and make the committed eval extractions stale, so it stays a reviewed file change. A live run takes 3 minutes and depends on the Find a Tender API, which is dead air on a call. Bid/no-bid capture is the shadow pilot's job.
- **Cost:** about 7 hours beyond the box. The MCP server adds one dependency (D38). Results are only as fresh as the last CLI run.
- **Revisit if:** a pilot starts: then add bid/no-bid capture and a small authenticated server, and consider a guarded run tool with the budget enforced.

## D37: One saved run record feeds both views
- **Chose:** every CLI run also writes `output/runs/<from>_<to>.json`, a Pydantic-validated record with a schema version, the run summary, a profile snapshot and every assessed notice with its lots, criteria, reasons, red flags and rationale. The web view and the MCP server read only this file.
- **Alternatives:** each view re-runs the pipeline from the saved notices and the extraction cache; the views parse `shortlist.csv`; a SQLite database.
- **Why:** re-running would give each view its own copy of the scoring path and need the LLM for rationales, which are not cached. The CSV flattens lots and criteria, which both views need. A database adds a schema and migrations for a weekly file. One JSON file per run is easy to commit as an example, validate on load and explain to a client.
- **Cost:** the record repeats data that is already in `report.md` and the CSV; a schema change needs a version bump and old runs either migrate or fail with a clear error.
- **Revisit if:** runs need querying across many weeks, or more than one person writes results.

## D38: The MCP server uses the official `mcp` SDK, version 2
- **Chose:** `mcp>=2.3`, the official Python SDK, for slice 7's stdio server. Version 2 renamed `FastMCP` (`mcp.server.fastmcp`, which the plan named) to `MCPServer` (`mcp.server.mcpserver`); the check the plan asked for before coding found the old import gone, so the server uses `MCPServer`.
- **Alternatives:** pin `mcp<2` and keep `FastMCP` as the plan wrote it; write the JSON-RPC stdio loop by hand; the separate `fastmcp` package.
- **Why:** the SDK negotiates protocol versions with each client, which a hand-written loop would have to track as the protocol changes. Pinning 1.x would start on a superseded major version for no gain, since the two APIs are close. Version 2 also connects a client to a server object in memory, so the tests run the real protocol without a subprocess. One-line reason: the official SDK for the MCP server the spec now includes (D36).
- **Cost:** 17 more packages in the lock file (among them starlette, uvicorn, cryptography and jsonschema), mostly for HTTP transports the server does not use.
- **Revisit if:** Claude Desktop or Claude Code cannot connect to a 2.x server; then pin `mcp<2` and switch to `FastMCP`.

## D39: The web view is a quiet Swiss-style report page with system fonts
- **Chose:** a minimal, light-first page in the "Minimalism & Swiss" style the `ui-ux-pro-max` design pass returned for a data-dense B2B report: one navy accent (#1e40af), slate text, amber only for red-flag chips and red only for the INCOMPLETE banner, a dark scheme from `prefers-color-scheme`. System font stack, 16 px base, a 1.75 / 1.25 / 1.06 / 0.94 rem heading scale and tabular numbers. Shortlisted notices are cards with a bullet bar (fill = score, tick = threshold, both also written as numbers); the other groups are tables that stack into labelled rows under 640 px. The score breakdown sits in `<details>`, so the page works without JavaScript; the script only switches groups and filters tables, through `hidden` and `textContent`. Lot status is shown as the record names it ("gated").
- **Alternatives:** the design pass's own font pairing (Fira Code and Fira Sans from Google Fonts) and GSAP list motion, both ruled out because the page must make no outside requests and needs no motion; a dashboard style with KPI tiles and charts, which spends the page on decoration for a list of 5 to 30 notices; one big table like the CSV, which has no room for the rationale; a red-to-green gauge per score, which leans on colour (the design pass's own chart guidance prefers a bullet bar with the number beside it).
- **Why:** the bid team reads a ranked list and decides what to open, so hierarchy and scanning matter more than visuals. A single file with no network opens offline, on a call, or as an attachment, and cannot leak that someone opened it. Escaping every string and never writing HTML from the script keeps planted notice text inert.
- **Cost:** system fonts look slightly different on Windows, macOS and phones. The score bar's track is a low-contrast shape in dark mode; the number and threshold beside it carry the meaning. No sorting or column choice: the table order is the report's.
- **Revisit if:** the team wants to act on the page (bid/no-bid, notes): that needs a server (D36's "Revisit if").

## D40: The demo week is 16–21 Nov, and its committed copy has one name masked by hand
- **Chose:** slice 9 ran 16–21 Nov (Monday to Saturday) on Sunday 22 Nov, and the copy committed to `examples/runs/` has one person's name replaced with `[name removed]` in three rejected notices' descriptions ("contact … on [phone removed]"). The run in `output/runs/` is untouched. The human chose both on 22 Nov.
- **Alternatives:** for the week, run 16–22 Nov on the 22nd, which would miss the rest of that day's notices without saying so, or wait for the 23rd as the plan said; for the name, commit the file as fetched (public text under OGL, and "names stay" is already a known limit), or commit nothing and demo from `output/` only.
- **Why:** a week that ends on the run day is silently incomplete, and running on the morning of the call leaves no time to read the result or recover from a failed run; few notices are published on a Sunday. The spec keeps personal data out unless it needs it, and a public repo is a wider audience than the source page. A hand edit of one file was cheaper and more certain than adding name detection to the pipeline the day before the call.
- **Cost:** the example does not show Sunday's notices, and it is no longer byte-for-byte what the pipeline wrote. Other names written in other forms may remain: the scan looked for titles (Mr, Dr) and names after contact words.
- **Revisit if:** run files are shared beyond this repo: then mask names in the pipeline, not by hand.

<!--
Template:
## Dn: <decision>
- **Chose:**
- **Alternatives:**
- **Why:**
- **Revisit if:**
-->
