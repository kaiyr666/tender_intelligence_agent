# Review 03

- **Date:** 2026-11-22
- **Mode:** all, whole repository against docs/SPEC.md (Codex gpt-6.2-sol, no reasoning effort, read-only, static: it could not run the tests)

## P1 — must fix

- [src/app/fetch.py:84](src/app/fetch.py:84) — If a later page returns HTTP 500 or invalid JSON, the CLI exits and loses all releases collected so far. Return the accumulated releases with `complete=False` on terminal page failures, and test that the CLI still writes an incomplete report.
- [src/app/score.py:72](src/app/score.py:72) — Both quote-backed gates search the entire notice, so an accreditation required only for one lot can wrongly disqualify another lot using a verbatim quote. Verify lot-level claims against the relevant lot’s text and verify notice-wide claims against notice-wide text. Add a mixed-lot regression test.
- [src/app/score.py:75](src/app/score.py:75) — An extraction can omit the only eligible lot or return conflicting duplicate entries and still produce a definitive shortlist or rejection. Require exactly one extraction for each expected lot ID, retry invalid coverage, and route persistent failures to needs review.
- [src/app/score.py:141](src/app/score.py:141) — Substring matching treats Cyber Essentials Plus as held when the profile contains only Cyber Essentials, allowing a shortlist entry that fails a mandatory requirement. Normalize scheme aliases and edition suffixes, preserve qualification levels, and match explicit alternatives individually.
- [src/app/notices.py:154](src/app/notices.py:154) — CPV collection skips an item’s primary `classification`, so a relevant notice can be dropped when its matching code appears there and its collected codes are outside the profile. Collect primary and additional CPV classifications in the shared parser and test that a match in either keeps the notice.
- [src/app/llm.py:95](src/app/llm.py:95) — The budget check treats three characters per input token as an upper bound and checks each SDK call only once even when the SDK retries internally, so spending can exceed the configured cap. Use a provider-aware input count or a conservative upper bound, disable SDK-managed retries, and reserve budget before each application-managed attempt.
- [src/app/__main__.py:73](src/app/__main__.py:73) — The report’s completion status reflects only the fetch, so a budget-limited run can publish a shortlist without an incomplete banner. Carry the budget-stop reason into the run summary and test the banner with a complete fetch and unprocessed notices.
- [src/app/report.py:144](src/app/report.py:144) — The Markdown report interpolates API-supplied IDs and URLs directly into links, allowing malformed or unsafe destinations into the bid team’s report. Escape link labels, validate and encode HTTP(S) destinations, and fall back to the canonical notice URL when validation fails.

## P2 — should fix

- [src/app/fetch.py:117](src/app/fetch.py:117) — `Retry-After` accepts only numeric seconds, so a valid HTTP-date on a 429 or 503 falls back to ten seconds and can trigger an early retry. Parse both header forms and test the resulting delay.
- [src/app/explain.py:20](src/app/explain.py:20) — Rationale validation accepts blank or arbitrary prose up to 800 characters, so unsupported claims can appear in a deliverable that promises two or three sentences grounded in extracted facts. Validate sentence count and nonblank content, and render factual claims from validated references to the supplied fields.
- [src/app/report.py:147](src/app/report.py:147) — The Markdown report hides the selected lot’s name on notices with exactly one named lot. Display the lot name whenever the source notice has a lot and add a single-lot report assertion.
- [README.md:57](README.md:57) — The limitations section says both labelled sets now have 100% recall, while the current tuning result is 7 of 8 after D34. Date the 100% result as pre-D34 and state the current figures.

This was a static review. The workspace virtual environment points to an unavailable Python executable, and the Windows Python launcher also failed, so I could not rerun pytest or the offline eval.

**Overall verdict:** Fix the P1 issues before relying on the weekly shortlist for bid decisions.
