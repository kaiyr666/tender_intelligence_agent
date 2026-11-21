# Evaluation

<!-- Updated by /eval. Numbers, not impressions. -->

## How we measure
- **Eval set:** `evals/cases.jsonl`, 42 real Find a Tender notices (sanitised copies in `evals/notices.json`), 16 bid and 26 no-bid.
  - **Tuning set (32):** 9–15 Nov 2026, chosen in slice 1 to cover the profile's services, other regions and near misses (9 dropped by the pre-filter at the time). Labels were drafted by an agent that did not read `src/`, then checked by the human against the client's answers (D22, D25, D27); `bid_lots` lists every lot the team would bid. The profile fixes of slice 4 (D28–D30) were made while looking at these notices.
  - **Check set (10):** northern notices added after tuning, nine from 2–8 Nov and one from 9–15 Nov, picked by region and title before the tool read them: six the pre-filter kept and four it dropped (all four kept since D32, so this set has now been used for tuning too). Labels drafted by Claude from the client's rules before any extraction, then checked by the human on 21 Nov: confirmed fire doors (105640) and damp treatment (105810) as bids, and added Wirral's Lot 5 (roof and window replacement) to `bid_lots`.
- **Run:** `uv run python -m evals.run` (offline, from the committed extractions in `evals/extractions/`; no API key, no cost). `--live` reads any missing notice with the LLM in `.env` (D31).
- **Judged at:** Mon 16 Nov 2026, 09:00 UTC (deadlines and "closed" are judged against this, not today).
- **Metrics:** "shortlisted" is the positive prediction; a bid that is rejected, sent to review or dropped by the pre-filter is a false negative. Pre-filter recall is the share of bids the pre-filter keeps. The lot check asks whether the chosen lot is in `bid_lots` and lists bid lots that were gated. Field accuracy compares the extraction of one labelled lot ("not stated" allowed; set match for services and accreditations; region as the scorer uses it, at NUTS 1); coverage is the share of cases that reached extraction. The sweep re-cuts the shortlist at other thresholds without new LLM calls.
- **Model:** `gpt-6.1-terra` (D15). Re-reading all 42 cost $0.19; the 6 notices D32 lets through cost about $0.03 more.

## Results
| Date | Set | Cases (bids) | Precision | Recall | Pre-filter recall | Chosen lot ok | Change |
|---|---|---|---|---|---|---|---|
| 2026-11-21 | Tuning | 32 (8) | 100% (8/8) | 100% (8/8) | 100% | 100% (8/8) | First measured run, threshold 0.70 |
| 2026-11-21 | Check | 10 (8) | 100% (4/4) | 50% (4/8) | 50% | 100% (4/4) | Not seen while tuning |
| 2026-11-21 | All | 42 (16) | 100% (12/12) | 75% (12/16) | 75% | 100% (12/12) | |
| 2026-11-21 | Tuning | 32 (8) | 100% (8/8) | 100% (8/8) | 100% | 100% (8/8) | Construction codes reach the LLM, £0 is not stated (D32) |
| 2026-11-21 | Check | 10 (8) | 100% (8/8) | 100% (8/8) | 100% | 100% (8/8) | Fixed on this set, so no longer independent |
| 2026-11-21 | All | 42 (16) | 100% (16/16) | 100% (16/16) | 100% | 100% (16/16) | |
| 2026-11-22 | Blind week | 137 (5) | 80% (4/5) | 80% (4/5) | 80% (4/5) | not checked | Unseen week 26 Oct–1 Nov, screened by the human, after review (D33) |

Targets: recall ≥ 80%, precision ≥ 60%. Before D32 they were met on the tuning set and **recall was missed on the check set** (50%), entirely through the pre-filter. After D32 both sets reach 100%, but both have now been used for fixes, so these figures show the fixes work, not how the tool does on unseen weeks. On the one unseen week (below) both targets are met after review, at 4 of 5, which is too few bids to call them met.

Field accuracy on all 42, after D32 (coverage 86%: the 6 notices still dropped by the pre-filter are not extracted):

| Field | Accuracy |
|---|---|
| Contract length | 100% |
| TUPE flag | 100% |
| Mandatory accreditations | 97% |
| Mobilisation | 97% |
| Region (as scored) | 94% |
| Primary service | 86% |
| Services | 81% |

Threshold sweep, tuning set: precision 100% throughout; recall 100% from 0.50 to 0.75, 88% at 0.80, 75% at 0.90. The threshold is 0.70 (D30): above the 0.65 that a lot of a service the company does not offer can reach, below every bid.

## Blind screen of an unseen week (26 Oct–1 Nov)
- **Method (D33):** `uv run python -m evals.blind make` listed the 137 notices open on Mon 2 Nov that were delivered in the North, UK-wide by lot or with no stated region, whatever their CPV code, leaving out the eval notices. The list showed notice facts only (title, buyer, value, delivery codes, deadline, the first 300 characters), in a fixed random order. The human marked each one bid, maybe or blank in about 1 hour, and the marks were committed (39d8de7) before the tool read the week. `evals.blind compare` then ran the real pipeline as at 2 Nov 09:00 (35 LLM calls, $0.19). The human reviewed every maybe and every disagreement against the full notice in 15 minutes (`evals/blind/2026-10-26_review.md`).

| Marks | Bids | Found | Missed | Shortlisted, not a bid | Precision | Recall |
|---|---|---|---|---|---|---|
| Blind, maybes as no | 2 | 2 | 0 | 3 | 40% (2/5) | 100% (2/2) |
| Blind, maybes as bid | 9 | 2 | 7 | 3 | 40% (2/5) | 22% (2/9) |
| After review | 5 | 4 | 1 | 1 | 80% (4/5) | 80% (4/5) |

- **Review groups:** 1 tool error, 0 missing rules, 8 marks changed by the human, 1 borderline.
  - **Tool error:** structural repairs to Blackpool Tower (102242; engineering and structural steel codes) were read as building maintenance and shortlisted at 0.95. It reached the LLM only through D32's construction codes: this is the precision risk D32 named.
  - **Changed marks:** six maybes became no for the reason the tool gave (Scotland, no region stated, not an offered service). Two blanks became bids once the lots were read: L&Q fire risk assessment remedials, Lot 3 North West (100987), and EEM's fire doors framework, a national-coverage lot (100829). The second also came in through D32.
  - **Borderline:** Newcastle bin and scooter stores (102758), supply and installation at housing blocks, coded 44000000 (construction products) and dropped by the pre-filter. The one miss.
- **How to read it:**
  - Five bids: each one moves recall or precision by 20 points, so these are counts, not rates.
  - The reviewed figures lean towards the tool: both blank-to-bid changes were made after seeing the tool shortlist them. Both rest on lot facts the 300-character summary did not show, but anchoring cannot be ruled out. The blind rows bound the result from the other side.
  - D32 on this week: one bid found (100829) and the one false positive (102242).
  - The human would bid a national-coverage lot whose delivery codes list every English region (100829). D25 and "Where it breaks" treat that as a weakness of the region gate, so the client's rule on national lots needs confirming.
- **Time:** the manual screen of 137 already narrowed notices took about 1 hour. The tool's shortlist was 5 notices; reviewing its 10 disagreements took 15 minutes.

## Instructive failures
1. **The CPV pre-filter dropped real bids** (check set, 3 of 8 bids; fixed by D32). Karbon Homes responsive repairs and voids (103529, codes 4542xxxx to 4545xxxx), Oldham building repair and maintenance (104445, only 45000000) and Northumbria term electrical services (103643, 45317300) never reach the LLM. Buyers code maintenance work with construction (45) codes. This is the "revisit if" of D1 and D12. The four dropped picks were chosen to test the pre-filter, so the check set overstates how often this happens, but it does happen.
2. **A value of £0 counted as a value** (105298, Greenhead College cleaning; fixed by D32). The notice gives £0 as a placeholder, and the pre-filter drops it as "under £100k". £0 should be read as "not stated".
3. **The primary service of out-of-scope notices is still unstable.** Northern Ireland's construction and minor works framework (106024) reads as building maintenance, a food hall operator (106859) as "other" instead of catering, and British Council FM in Bangladesh (107354) as "other" instead of integrated FM. None changes an outcome (region or another gate decides), but it shows where the service definitions still leave room.

Smaller misses: 108100's 6-week mobilisation was not extracted; MDSAP was written out in full (108075); a delivery list that covers most of England is taken as the region (108109, 105503; see "Where it breaks").

## What would improve it most
- **A shadow pilot:** the bid team runs the tool beside its manual screen for 3 to 4 weeks and records its own decisions next to the CSV, about 20 to 30 real bid decisions. One blind week gave 5 bids; about 60 would pin recall to within ±10 points.
- Separate structural and heritage repair (engineering, structural steel) from building maintenance in the service definitions, and confirm the rule for national-coverage lots.
- Apply the region gate in the pre-filter when a notice has delivery addresses: after D32 most of the extra LLM calls are notices the region gate rejects anyway.
