# Evaluation

<!-- Updated by /eval. Numbers, not impressions. -->

## How we measure
- **Eval set:** `evals/cases.jsonl`, 42 real Find a Tender notices (sanitised copies in `evals/notices.json`), 16 bid and 26 no-bid.
  - **Tuning set (32):** 9–15 Nov 2026, chosen in slice 1 to cover the profile's services, other regions and near misses (9 dropped by the pre-filter at the time). Labels were drafted by an agent that did not read `src/`, then checked by the human against the client's answers (D22, D25, D27); `bid_lots` lists every lot the team would bid. The profile fixes of slice 4 (D28–D30) were made while looking at these notices.
  - **Check set (10):** northern notices added after tuning, nine from 2–8 Nov and one from 9–15 Nov, picked by region and title before the tool read them: six the pre-filter keeps and four it drops. Labels drafted by Claude from the client's rules before any extraction, then checked by the human on 21 Nov: confirmed fire doors (105640) and damp treatment (105810) as bids, and added Wirral's Lot 5 (roof and window replacement) to `bid_lots`.
- **Run:** `uv run python -m evals.run` (offline, from the committed extractions in `evals/extractions/`; no API key, no cost). `--live` reads any missing notice with the LLM in `.env` (D31).
- **Judged at:** Mon 16 Nov 2026, 09:00 UTC (deadlines and "closed" are judged against this, not today).
- **Metrics:** "shortlisted" is the positive prediction; a bid that is rejected, sent to review or dropped by the pre-filter is a false negative. Pre-filter recall is the share of bids the pre-filter keeps. The lot check asks whether the chosen lot is in `bid_lots` and lists bid lots that were gated. Field accuracy compares the extraction of one labelled lot ("not stated" allowed; set match for services and accreditations; region as the scorer uses it, at NUTS 1); coverage is the share of cases that reached extraction. The sweep re-cuts the shortlist at other thresholds without new LLM calls.
- **Model:** `gpt-6.1-terra` (D15). Re-reading all 42 cost $0.19.

## Results
| Date | Set | Cases (bids) | Precision | Recall | Pre-filter recall | Chosen lot ok | Change |
|---|---|---|---|---|---|---|---|
| 2026-11-21 | Tuning | 32 (8) | 100% (8/8) | 100% (8/8) | 100% | 100% (8/8) | First measured run, threshold 0.70 |
| 2026-11-21 | Check | 10 (8) | 100% (4/4) | 50% (4/8) | 50% | 100% (4/4) | Not seen while tuning |
| 2026-11-21 | All | 42 (16) | 100% (12/12) | 75% (12/16) | 75% | 100% (12/12) | |

Targets: recall ≥ 80%, precision ≥ 60%. Met on the tuning set, which the fixes were made on; **recall is missed on the check set**, entirely through the pre-filter.

Field accuracy on all 42 (coverage 71%: the 12 notices dropped by the pre-filter are not extracted):

| Field | Accuracy |
|---|---|
| Contract length | 100% |
| TUPE flag | 100% |
| Mandatory accreditations | 97% |
| Mobilisation | 97% |
| Region (as scored) | 93% |
| Primary service | 87% |
| Services | 83% |

Threshold sweep, tuning set: precision 100% throughout; recall 100% from 0.50 to 0.75, 88% at 0.80, 75% at 0.90. The threshold is 0.70 (D30): above the 0.65 that a lot of a service the company does not offer can reach, below every bid.

## Instructive failures
1. **The CPV pre-filter drops real bids** (check set, 3 of 8 bids). Karbon Homes responsive repairs and voids (103529, codes 4542xxxx to 4545xxxx), Oldham building repair and maintenance (104445, only 45000000) and Northumbria term electrical services (103643, 45317300) never reach the LLM. Buyers code maintenance work with construction (45) codes. This is the "revisit if" of D1 and D12. The four dropped picks were chosen to test the pre-filter, so the check set overstates how often this happens, but it does happen.
2. **A value of £0 counts as a value** (105298, Greenhead College cleaning). The notice gives £0 as a placeholder, and the pre-filter drops it as "under £100k". £0 should be read as "not stated".
3. **The primary service of out-of-scope notices is still unstable.** Northern Ireland's construction and minor works framework (106024) reads as building maintenance, a food hall operator (106859) as "other" instead of catering, and British Council FM in Bangladesh (107354) as "other" instead of integrated FM. None changes an outcome (region or another gate decides), but it shows where the service definitions still leave room.

Smaller misses: 108100's 6-week mobilisation was not extracted; MDSAP was written out in full (108075); a delivery list that covers most of England is taken as the region (108109, 105503; see "Where it breaks").

## What would improve it most
- **Let construction-coded maintenance through the pre-filter**, for example keep 45000000 and the 4542/4543/4544/4545 building-completion codes when the title or description says "repair" or "maintenance", or send 45 codes to a cheap LLM relevance check (D1). Measure on the check set, then label a fresh week, because the check set would then have been used for tuning.
- Treat a value of £0 as unknown.
