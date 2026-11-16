# CLAUDE.md

## Project
<!-- /spec fills this section in from the brief. Keep it to five lines. -->
- **What:** a CLI that pulls UK Find a Tender notices for a date range, filters and scores them against a company profile, and writes a ranked, explained shortlist (Markdown + CSV).
- **For whom:** the bid team of a UK facilities-management company (cleaning, security, building maintenance).
- **In scope / out of scope:** see `docs/SPEC.md`
- **Run:** `uv run python -m app --from YYYY-MM-DD --to YYYY-MM-DD`
- **Test:** `uv run pytest`

## How we work
1. Read `docs/SPEC.md`, `docs/PLAN.md` and `docs/DECISIONS.md` before starting any task. They are the source of truth, not this conversation.
2. If the brief or spec is unclear, or a task conflicts with the spec, stop and ask. Do not guess.
3. Build one slice from `docs/PLAN.md` at a time. A slice is a small piece that works end to end and can be shown.
4. Each real design choice goes in `docs/DECISIONS.md`: what we chose, the alternative, and why it lost.
5. Log in `docs/AI_WORKFLOW.md` anything notable: what was delegated, what a review flagged, what the human overruled.
6. After each slice: commit, push to GitHub, report what was built and the test results, then stop and wait.

## Engineering rules
- **Simplest thing that works.** No extra features, layers or libraries. Put "with more time" ideas in the README's next steps instead of building them.
- **Code for exact things, LLM for messy text.** Filters, scores, matching and numbers are deterministic Python. The LLM only reads unstructured text or writes explanations.
- **All LLM calls go through `src/app/llm.py`.** Prompts live in `src/app/prompts/*.md`. Output is JSON validated against a Pydantic model before use.
- **Never call a real LLM in tests.** Use the fake provider in `tests/conftest.py`.
- **Secrets:** never read, write or print `.env` or API keys. Keys come from environment variables only.
- **New dependency:** only with a one-line reason in `docs/DECISIONS.md`. Add it with `uv add`.
- **Readable over clever.** Clear names, short functions, a docstring only where the why is not obvious. The human must be able to explain this code to a client.
- **Personal data:** do not store or log names, emails or other personal data unless the spec requires it.

## Definition of done (per slice)
- [ ] Tests for the new behaviour exist and `uv run pytest` passes
- [ ] `uv run ruff check .` is clean (formatting runs automatically)
- [ ] `docs/PLAN.md` ticked, `docs/DECISIONS.md` updated if a choice was made
- [ ] Known limitations added to "Where it breaks" in `README.md`
- [ ] If the slice touches anything the eval measures, `/eval` re-run
- [ ] One commit: `slice N: <what it does>`, pushed with `git push`

## Commands
`/setup` first-time setup · `/spec` brief → spec and plan · `/slice` build the next slice · `/codex-review` independent review by Codex · `/eval` measure quality · `/wrapup` final README and release
