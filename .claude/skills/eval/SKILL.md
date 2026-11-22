---
name: eval
description: Measure how well the system works on a labelled set of examples and record the results in docs/EVAL.md. Use when the user types /eval or a slice changes what the eval measures.
disable-model-invocation: true
---

Measure quality with numbers, not impressions.

## Steps
1. **Check the eval set:** `evals/cases.jsonl` holds one example per line: `{"id": ..., "input": ..., "expected": {...}}`. If it still holds the kit's sample cases, build a real set first: 20 to 40 examples from the project's data, covering normal cases, edge cases and known hard cases. Expected answers must come from the data or the user, never from the system under test. If the labels need human judgement, draft them and ask the user to check a sample.
2. **Connect the harness:** `evals/run.py` runs the real pipeline on each case and scores each expected field. Adjust the scoring only if exact match is wrong for a field (for example, a numeric tolerance), and note why in `docs/DECISIONS.md`.
3. **Run it:** `uv run python -m evals.run`. This writes `evals/results/latest.json` and prints a summary.
4. **Update `docs/EVAL.md`:** date, number of cases, the score for each metric, a comparison with the previous run if there is one, and the three most instructive failures with the reason for each.
5. **Report** the headline numbers and the main failure pattern in under 8 lines, and suggest the single change most likely to improve the score.

Never tune prompts or code against individual eval cases just to pass them. If you add cases after seeing failures, say so in `docs/EVAL.md`.
