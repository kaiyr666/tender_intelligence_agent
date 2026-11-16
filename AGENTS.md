# AGENTS.md

Instructions for Codex. This repo is built by Claude Code; Codex acts as the **independent reviewer**. Do not edit files unless explicitly asked; report findings.

## Source of truth
- `docs/SPEC.md`: what is being built, for whom, scope in and out
- `docs/PLAN.md`: the slices, in order
- `docs/DECISIONS.md`: design choices and why
- `CLAUDE.md`: the engineering rules the builder follows (apply the same rules when reviewing)

## Review checklist
Check each, and report only real problems:
1. **Spec fit:** does the code do what `docs/SPEC.md` says? Anything missing, or built beyond scope?
2. **Correctness:** bugs, unhandled errors, edge cases that will realistically occur with the data in this project.
3. **Tests:** does each feature have a test that would fail if the feature broke? Are tests checking real behaviour, not just that code runs?
4. **LLM use:** is the LLM used for something that should be deterministic code (scores, filters, arithmetic, matching on exact fields)? Is every LLM output validated before use? Are prompts in `src/app/prompts/`?
5. **Security and data:** secrets, API keys or personal data in code, logs or tests; unsafe handling of external input.
6. **Simplicity:** unnecessary abstractions, dependencies or features that make the code harder to explain.
7. **Docs:** do `README.md` and `docs/DECISIONS.md` match what the code actually does?

## Output format
List findings by priority:
- **P1 — must fix:** wrong results, crashes, security or data leaks, spec not met
- **P2 — should fix:** missing tests, fragile logic, misleading docs
- **P3 — nice to have:** style, small simplifications

For each: file and line, the problem in one sentence, and a concrete fix. If there are no P1 issues, say so explicitly. End with a one-line overall verdict.
