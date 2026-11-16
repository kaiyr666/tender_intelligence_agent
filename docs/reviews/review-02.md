# Review 02

- **Date:** 2026-11-16
- **Mode:** plan (Codex gpt-6-astra, high reasoning effort, read-only)

The **fixed workflow is the right approach**: deterministic filtering and scoring, with LLMs handling free-text extraction and explanations. Retrieval and autonomous agents are unnecessary for this proof of concept. Deferring MCP, incumbent lookup, and a UI is sensible.

The scope is plausible as a tightly constrained demonstration, but the current plan is optimistic for five hours. I found two P1 gaps in the proposed design.

1. **P1 — Must fix: eligibility is not consistently evaluated per lot.**  
   [docs/DECISIONS.md:30](../DECISIONS.md:30) specifies lot-level region and value, while service and accreditation gates remain unspecified at lot level. A notice containing a suitable office-cleaning lot and an excluded hospital-cleaning lot could therefore reject the suitable opportunity or combine incompatible facts.  
   **Fix:** retain service, eligibility requirements, region, and value against each lot ID; apply gates and scoring to each candidate lot before selecting the best eligible one. Add a mixed-lot regression test. One report row per notice remains appropriate.

2. **P1 — Must fix: the evaluation cannot measure extraction accuracy from the planned labels.**  
   [docs/PLAN.md:17](../PLAN.md:17) provides bid/no-bid labels and reasons, but promises per-field extraction accuracy without defining expected field values.  
   **Fix:** add human-checked reference values for the extracted fields, including unknowns and lot IDs, with explicit comparison rules for dates, durations, and accreditation sets. If only a subset can be annotated within the time box, report that coverage explicitly.

3. **P2 — Should fix: evaluation design risks overstating shortlist quality.**  
   [docs/SPEC.md:16](../SPEC.md:16) tunes the threshold on the same evaluation set, and [docs/PLAN.md:17](../PLAN.md:17) deliberately selects near misses. Those results would not establish expected weekly precision and recall.  
   **Fix:** separate calibration cases from untouched evaluation cases; distinguish representative sampling from an edge-case challenge set. Evaluate the entire pipeline, including pre-filter rejects, and freeze the evaluation date so deadline filtering is reproducible. With approximately 30 cases, report TP/FP/FN counts and describe results as preliminary.

4. **P2 — Should fix: the schedule discovers the most consequential risks too late.**  
   [docs/PLAN.md:3](../PLAN.md:3) allocates 235 minutes across the slices, leaving 65 minutes for specification, review checkpoints, human labelling, and overruns; evaluation starts only after reporting is built.  
   **Fix:** begin with a short data-and-evaluation discovery step: inspect real notices, select cases, start human checking, and measure one extraction call. Then build a small end-to-end report before expanding coverage. Reserve explicit time for evaluation fixes and fresh-clone verification. This also resolves the mismatch with `CLAUDE.md`, which requires evaluation after relevant slices.

5. **P2 — Should fix: the $5 budget depends on unverified volume and missing usage accounting.**  
   [docs/SPEC.md:28](../SPEC.md:28) treats the team’s 150–250 weekly notices as the API’s pre-filter volume, although the brief only establishes how many the team reads; [docs/PLAN.md:9](../PLAN.md:9) promises cost logging, but the existing provider discards token usage.  
   **Fix:** measure fetched volume, survivors, and representative token consumption during discovery. Extend the wrapper to record usage across extraction, rationale, and retries; budget evaluation and label drafting explicitly. Check remaining budget before calls and report incomplete processing if the limit is reached.

6. **P2 — Should fix: schema validation is being treated as sufficient evidence for hard rejection.**  
   [docs/SPEC.md:13](../SPEC.md:13) validates extraction through Pydantic, but a structurally valid answer can still invent a mandatory accreditation or misidentify the primary service. Feeding that extraction into the rationale step preserves the error.  
   **Fix:** require source evidence and lot IDs for fields that trigger gates, represent uncertainty explicitly, and send unsupported eligibility conclusions to manual review. Add tests for absent requirements, optional versus mandatory wording, and misleading instructions embedded in notice text. Evidence checks support traceability; human-labelled evaluation still establishes accuracy.

7. **P2 — Should fix: the fetch contract does not define what counts as a new opportunity.**  
   [docs/PLAN.md:5](../PLAN.md:5) covers paging and normalisation but leaves release updates, duplicate opportunities, withdrawals, and date boundaries unspecified; it also promises planning counts without explicitly planning their retrieval.  
   **Fix:** inspect real responses and define whether the report covers newly published or updated opportunities, the identity used for deduplication, and how current status is resolved. Define inclusive CLI dates and the planning-stage query. Add fixtures for multiple releases of one opportunity and a withdrawn notice.

8. **P2 — Should fix: there is no explicit partial-failure behaviour.**  
   [docs/PLAN.md:8](../PLAN.md:8) assumes every surviving notice receives validated fields, without defining what happens after extraction retries fail or fetching stops partway through.  
   **Fix:** distinguish “rejected,” “needs review,” and “not processed.” Bound network retries and timeouts, preserve completed work, and visibly mark incomplete reports. Test one failed extraction among successful notices and an interrupted paginated fetch; neither should silently produce an apparently complete shortlist.

9. **P3 — Nice to have: the architecture rationale overstates the drawbacks of alternatives.**  
   [docs/DECISIONS.md:8](../DECISIONS.md:8) says an agent would let the LLM decide scores and describes retrieval only as a similarity score; neither is inherent to those approaches.  
   **Fix:** justify the workflow through the actual requirements: a bounded sequence, one source, deterministic business rules, and no need for autonomous tool selection. Retrieval can remain a future candidate-discovery option if measured recall warrants it.

**Overall verdict:** sound architecture and sensible exclusions, but revise lot eligibility, evaluation design, and slice order before building; five hours supports a demonstrable prototype with preliminary evidence, not yet a validated weekly screening tool.
