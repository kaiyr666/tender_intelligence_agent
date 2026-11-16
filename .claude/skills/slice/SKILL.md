---
name: slice
description: Build the next unfinished slice from docs/PLAN.md, test it, commit it, then stop for the user's check. Use when the user types /slice or says "next".
disable-model-invocation: true
argument-hint: "[optional slice number, default: next unticked one]"
---

Build exactly one slice, then stop.

## Steps
1. **Re-read the source of truth:** `docs/SPEC.md`, `docs/PLAN.md`, `docs/DECISIONS.md`. Pick slice $ARGUMENTS, or the first unticked slice. If the plan is empty, tell the user to run `/spec` first and stop.
2. **Say the plan in three lines:** what you will build, which files you expect to touch, how you will test it. Then go ahead without waiting unless something conflicts with the spec. In that case, stop and ask.
3. **Tests.** For the core logic, write the test first, from the spec. Use the `test-writer` subagent if the logic is non-trivial, so the tests are written without seeing the implementation. Never call a real LLM in tests; use the `fake_llm` fixture.
4. **Build** the simplest version that meets the slice goal. Follow the engineering rules in `CLAUDE.md`.
5. **Check:** `uv run pytest -q` and `uv run ruff check .` must pass. If this slice changes anything the eval measures and an eval exists, run `/eval`.
6. **Update docs:** tick the slice in `docs/PLAN.md`; add any design choice to `docs/DECISIONS.md`; add known limitations to "Where it breaks" in `README.md`; add a line to `docs/AI_WORKFLOW.md` if anything notable happened (a wrong turn, a bug the tests caught, a choice the user overruled).
7. **Commit and push:** commit as `slice N: <what it does>`, then `git push`. If the push fails, tell the user why (usually not signed in to GitHub: see `docs/kit/SETUP.md`) and carry on; the work is safe locally.
8. **Stop and report** in under 10 lines: what works now, how to see it (one command to run), test results, anything you were unsure about. End with: "Check it, then `/slice` for the next one or tell me what to fix."
