# How AI was used

This project was built AI-first: **Claude Code** wrote the code under a written spec and plan, with automatic checks on every edit; **Codex** reviewed the work independently; the human set scope, approved each step and made the judgement calls.

## Setup
- Builder: Claude Code, following `CLAUDE.md`
- Reviewer: Codex, following `AGENTS.md`; reviews saved in `docs/reviews/`
- Automatic checks: formatting and lint on every edit, tests at the end of every turn, secret blocking, CI on every push

## Log
<!-- One line per notable event: what was delegated, what a review or test caught, what the human overruled and why. -->
| Step | What happened | Human decision |
|---|---|---|
| Spec | Claude turned the brief into a spec, a 5-slice plan and 7 decisions, and asked four scoping questions first (lots, hard gates, shortlist cut, stretch items). | Chose one row per notice scored on its best lot, a score threshold, and no stretch items. Overruled the brief's reading on gates: only value < £100k, excluded main service and missing accreditation drop a tender; out of region and over £5m just lower the score. |
| Plan review 01–02 | Codex reviewed the spec and plan twice: 12 findings on `gpt-6.1-sol` (no reasoning), then 9 on `gpt-6-astra` (high reasoning), which the human asked for. They largely agreed; the second added partial-failure handling, the missing planning-stage fetch, a frozen eval date and the fact that `llm.py` discards token usage. Fixed in the spec and plan: per-lot gating and scoring, expected field values in the eval, masking contacts in free text, CPV fallback, release de-duplication, cost control before calls, discovery moved to the start of slice 1, a time buffer, and D1 reworded. | Approved Claude's recommendations. Rejected: a held-out eval split (30 cases is too few, D9) and a timed bid-manager review (needs a real user). Supporting quotes were limited to the two LLM-driven gates (D8). All three are noted in the README. |
| Slice 1 | Discovery on the live API showed `stages=tender` returns 41 of over 500 tender releases (D11), and checking real CPV codes led to the matching rule in D12. The `test-writer` agent wrote about 95 tests from the spec without seeing the code. It caught a wrong expectation in Claude's brief (a notice listed as having no value has a gross value) and the missing expression-of-interest deadline, now handled (D13). Claude also fixed a bug in the kit's lint and test hooks: they decoded output with the Windows code page and crashed on the Cyrillic user folder. | No decisions needed. One extraction call was not costed because no API key is set; that moves to slice 2. |
