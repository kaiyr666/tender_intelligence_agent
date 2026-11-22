---
name: codex-review
description: Get an independent review from Codex (a different AI model) of the plan, the new work since the last review, or the whole repo. Use when the user types /codex-review.
disable-model-invocation: true
argument-hint: "[plan | all | empty = changes since last review]"
---

Ask Codex for an independent review, then help the user decide what to fix. **Do not fix anything until the user chooses.**

## 1. Run the review
Every command names the model and reasoning effort, so a review never falls back to Codex's defaults (on 22 Nov that was `gpt-6.2-sol` with no reasoning effort). `gpt-6.2-astra` is Codex's most capable model; raise the effort to `xhigh` for a pre-release whole-repo review if time allows.

First commit any uncommitted work so the review sees it. Then run one of these and wait for it to finish (it can take a few minutes):

- **`plan`:** critique the spec and plan before building:
  ```
  codex exec -m gpt-6.2-astra -c model_reasoning_effort="high" --sandbox read-only "Read AGENTS.md, docs/BRIEF.md, docs/SPEC.md, docs/PLAN.md and docs/DECISIONS.md. Critique the plan as a senior engineer and consultant: is the scope realistic for the time box, is the approach (plain software, workflow, retrieval or agent) right for the problem, what is missing or risky, and is the slice order sensible? Prioritise findings P1/P2/P3 as described in AGENTS.md."
  ```
- **empty (default):** review the code changed since the last review:
  ```
  codex exec -m gpt-6.2-astra -c model_reasoning_effort="high" --sandbox read-only "Review the code changed since the last review: the diff from the git branch 'reviewed' to HEAD (git diff reviewed..HEAD). Check it against docs/SPEC.md and the slices it builds in docs/PLAN.md. Follow the review checklist and output format in AGENTS.md."
  ```
  (Not `codex exec review --base reviewed`: Codex 0.169 refuses `--base` together with a prompt, and the prompt is what asks for AGENTS.md's format.)
- **`all`:** review the whole repository:
  ```
  codex exec -m gpt-6.2-astra -c model_reasoning_effort="high" --sandbox read-only "Review this entire repository against docs/SPEC.md, following the review checklist and output format in AGENTS.md."
  ```

If `codex` is not logged in or not installed, tell the user to run `codex login` (see `docs/kit/SETUP.md`) and stop.

## 2. Save and summarise
1. Save Codex's full output to `docs/reviews/review-NN.md` (next number), with the date, the mode, the model and the reasoning effort at the top (copy the last two from the `model:` and `reasoning effort:` lines Codex prints).
2. Show the user a short table: priority, finding, your recommendation (fix now / note in "Where it breaks" / disagree). Say plainly where you think Codex is wrong and why.
3. Ask which findings to fix.

## 3. After the user decides
- Fix the chosen findings, run the checks, commit `review NN: fix <summary>` and `git push`.
- Add findings not fixed to "Where it breaks" or "Next steps" in `README.md`.
- Add one line to `docs/AI_WORKFLOW.md`: number of findings, what was fixed, what was rejected and why.
- For code reviews (not `plan`), move the baseline: `git branch -f reviewed HEAD`.
