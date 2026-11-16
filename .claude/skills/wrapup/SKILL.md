---
name: wrapup
description: Final pass before delivery. Make the README complete and honest, check all docs, run all checks and tag a release. Use when the user types /wrapup.
disable-model-invocation: true
---

Prepare the repo for the people who will review it. They will read the README first, then the decisions, then the code.

## Steps
1. **Run everything:** `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run python -m evals.run` if an eval exists. Fix anything that fails.
2. **Complete `README.md`** following `docs/kit/README_TEMPLATE.md`: problem; what is built; how to run it (copy-paste commands that work on a fresh clone); architecture (a short text diagram plus why this approach); evaluation results (numbers from `docs/EVAL.md`); where it breaks; next steps if this were a paid engagement; how AI was used (link to `docs/AI_WORKFLOW.md`).
3. **Draft, don't decide, the judgement sections.** Write "Where it breaks" and "Next steps" as drafts and tell the user to edit them personally. They will be questioned on these.
4. **Check consistency:** README, `docs/SPEC.md`, `docs/DECISIONS.md` and the code agree. Every limitation found in reviews is either fixed or listed.
5. **Check hygiene:** no secrets, no `.env`, no large data files, no leftover debug code or commented-out blocks, and `.env.example` lists every variable the code reads.
6. **Commit** `wrapup: final docs` and tag `git tag v1.0`.
7. **Push:** `git push && git push --tags`.
8. **Report** a checklist of what the reviewer will see, and ask the user to open the repo on GitHub and check the CI tick is green.
