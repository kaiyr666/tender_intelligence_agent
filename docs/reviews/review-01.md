# Review 01

- **Date:** 2026-11-16
- **Mode:** plan (Codex, read-only)

The fixed workflow is the right approach: deterministic filtering and scoring, with an LLM interpreting free text and writing explanations. An autonomous agent adds little here, and retrieval is optional candidate discovery rather than a replacement for the rubric. Excluding MCP, incumbent lookup and a UI is sensible.

The scope is plausible for a demonstration, but the current plan is too tight for a validated five-hour PoC.

**P1 — must fix**

1. **Lot selection can combine incompatible requirements into a false recommendation.** [SPEC.md:15](../SPEC.md:15) specifies lot-specific region and value, but leaves services, accreditations, eligibility and mobilisation at notice level; this could combine a northern cleaning lot’s location with another lot’s requirements. **Fix:** evaluate each lot with all applicable criteria and notice-wide requirements, then select the best eligible lot; test a mixed cleaning/construction notice.

2. **The plan cannot measure extraction accuracy with the labels it proposes.** [PLAN.md:17](../PLAN.md:17) provides bid/no-bid labels and reasons, but no reference answers for extracted fields. **Fix:** add human-checked field labels, including “not stated,” and define matching rules for services, regions, dates, durations and accreditation requirements.

3. **Privacy protection is narrower than the stated prohibition.** [SPEC.md:11](../SPEC.md:11) sanitises `parties[]` while retaining notice text, which could itself contain contact names, emails or phone numbers. **Fix:** use a minimal persisted representation, redact contact details from retained text before storage or logging, and test contacts embedded in descriptions as well as structured fields.

**P2 — should fix**

4. **The time budget leaves little room for the highest-risk work.** [PLAN.md:3](../PLAN.md:3) allocates 235 minutes across slices, leaving only 65 minutes for specification, human label review, slice handoffs and unexpected failures. **Fix:** reserve explicit discovery, human-review and contingency time; simplify report presentation and polish before reducing evaluation or correctness work.

5. **Evaluation arrives after decisions it needs to inform.** [PLAN.md:15](../PLAN.md:15) postpones evaluation until filtering, scoring and reporting are built, despite CPV coverage and field availability being central uncertainties. **Fix:** select and begin labelling cases during slice 1; run a small extraction-and-scoring experiment before completing slice 2, then evaluate incrementally.

6. **The proposed evaluation can hide missed opportunities and overstate performance.** [PLAN.md:17](../PLAN.md:17) combines deliberately selected near misses with threshold tuning and final measurement on the same set. **Fix:** include notices from before the CPV filter, separate challenge cases from a representative sample, and reserve untouched cases for final measurement; report confusion counts and acknowledge the small sample.

7. **CPV rejection has no defined conservative fallback.** [SPEC.md:12](../SPEC.md:12) does not say what happens with missing, broad or conflicting notice/lot CPV codes, risking irreversible rejection before the LLM sees unexpectedly worded opportunities. **Fix:** inspect relevant codes across notice, items and lots, retain ambiguous cases, and measure pre-filter recall separately.

8. **Release handling and date semantics are unspecified.** [PLAN.md:5](../PLAN.md:5) plans paging and normalisation without defining how updates, duplicate releases, cancellations or date boundaries become one current opportunity. **Fix:** establish those rules from the initial API sample, distinguish new publication from subsequent updates, and test repeated releases and Sunday boundary cases.

9. **Schema validation does not establish factual support or define failure behaviour.** [PLAN.md:9](../PLAN.md:9) validates extraction structure but omits unsupported assertions, invalid responses and exhausted retries. **Fix:** require unknown values and supporting text for gate-driving fields, bound retries, and show unresolved extraction failures in a review section; validate rationale output too.

10. **A cost log detects overspending after it happens.** [PLAN.md:9](../PLAN.md:9) does not specify a shared budget covering the weekly run, evaluation, retries and tuning. **Fix:** estimate cost from a real sample before the full run, cache results, cap input/output sizes and stop before exhausting the combined budget.

**P3 — nice to have**

11. **The architecture justification overstates the limitations of alternatives.** [DECISIONS.md:8](../DECISIONS.md:8) implies retrieval cannot support explainable scoring and an agent necessarily decides scores. **Fix:** justify the workflow through its bounded task, predictable execution and lower implementation effort; retrieval could later improve candidate discovery while preserving deterministic scoring.

12. **The usability proxy does not verify the business outcome.** [SPEC.md:34](../SPEC.md:34) substitutes short rows for the promised 15-minute review. **Fix:** time one bid-manager review of a weekly report and record shortlist size, decisions made and confusing entries.

**Overall verdict:** Keep the workflow architecture, but move data discovery and evaluation forward, resolve lot-level correctness and privacy, and budget explicitly for validation before treating this as a credible five-hour PoC.
