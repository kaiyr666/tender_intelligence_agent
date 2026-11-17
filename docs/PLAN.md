# Plan

About 210 minutes of slices. The rest of the 5 hours covers the spec (done), the human's label check (~15 min) and about 30 minutes of contingency. If time runs short, cut report polish before evaluation or correctness.

- [x] **Slice 1: Discovery, fetch and pre-filter** (~60 min). Done; findings in D11–D14. The cost of one extraction call was not measured (no API key yet), so it moves to the start of slice 2. Weights and threshold join `config/profile.toml` in slice 2, where they are used.
  - Goal: know what the real data looks like, and see which notices survive the code pre-filter for a date range.
  - Discovery first (~15 min): fetch one real week; record the notice count, field coverage (value, deadline, lots, CPV, delivery addresses), how repeated releases and withdrawals appear; run one extraction call to measure tokens and cost. Write the findings in `docs/DECISIONS.md` and pick about 30 eval notices (including some the pre-filter drops), cached as sanitised fixtures.
  - Build: `fetch.py` (tender and planning stages, paging, timeout, bounded retries with `Retry-After`, latest release per `ocid`, withdrawn dropped, partial fetch marked incomplete); sanitising (parties cut to organisation and role, emails and phones masked in text); a `Notice` model; `config/profile.toml`; `prefilter.py` (CPV across notice, items and lots; no CPV is kept); the CLI prints counts by reason.
  - Test: a fake HTTP layer for paging, 429 and an interrupted fetch; two releases of one notice; a withdrawn notice; a contact email inside a description; pre-filter cases (closed deadline, < £100k, unknown value kept, unknown deadline kept, CPV only on a lot, no CPV kept, planning stage).
- [x] **Slice 2: Extract and score** (~60 min). Done, decisions D15–D21; the provider moved to OpenAI at the human's request. A real extraction cost $0.005 (D15). Draft labels are in `evals/labels_draft.jsonl` for the human to check before slice 4.
  - Goal: every pre-filtered notice ends up scored, rejected with a reason, or marked for review.
  - Build: `prompts/extract.md` and a per-lot `Extraction` model with supporting quotes for gate fields; token usage recorded in `llm.py`; an extraction cache; a budget check before each call; `score.py` (gates and weighted rubric per lot, best eligible lot chosen, quote check for LLM-driven gates). Draft eval labels and expected fields alongside, for the human to check.
  - Test: the fake provider; a mixed notice (office-cleaning lot plus hospital-cleaning lot) shortlists on the good lot; each gate and criterion; unknown value is neutral; a gate with no matching quote goes to "needs review"; optional versus mandatory accreditation wording; instructions embedded in notice text are ignored; one failed extraction among good ones; budget reached leaves the rest "not processed".
- [x] **Slice 3: Explain and report** (~30 min). Done, decisions D23–D24. The 9–15 Nov run gave 28 rationales for $0.03.
  - Goal: the bid team gets the full weekly output.
  - Build: `prompts/rationale.md` (from extracted fields only); `report.py` writing `output/report.md` and `output/shortlist.csv` with the four groups, planning count, cost, incomplete banner and OGL attribution. Plain layout, no polish. Run on the last full week.
  - Test: a golden-file test of the report and CSV from a fixed scored input; the rationale prompt gets no raw notice text.
- [ ] **Slice 4: Evaluation** (~40 min)
  - Goal: measure the shortlist and the extraction against the targets.
  - Build: `evals/cases.jsonl` with the human-checked labels and expected fields ("not stated" allowed; set match for services and accreditations, exact region, dates to the day, durations in months); the harness runs the whole pipeline, pre-filter included, against a frozen date and reports TP/FP/FN, precision, recall, pre-filter recall, per-field accuracy with coverage, and cost; threshold tuned; results in `docs/EVAL.md`, described as preliminary.
  - Test: the eval runs from a clean clone on cached notices.
- [ ] **Slice 5: Wrap-up** (~20 min)
  - Goal: a repo a reviewer understands in five minutes.
  - Build: README (how it works, results, where it breaks, next steps) and the final AI_WORKFLOW log.
  - Test: the fresh-clone instructions work.
