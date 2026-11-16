# ai-native-starter

A ready-made project folder for building small AI products fast and properly: **Claude Code builds, Codex reviews, the human decides.** Designed for time-boxed work such as a 5-hour take-home case or a pre-sales proof of concept.

`/spec` replaces this README with the project's own README (from `docs/kit/README_TEMPLATE.md`).

## What's inside

| Part | What it does |
|---|---|
| `CLAUDE.md` | The brief and rules for Claude Code: method, engineering rules, definition of done |
| `AGENTS.md` | The same rules for Codex, plus its review checklist |
| `.claude/hooks/` | Automatic checks: format and lint after every edit, tests at the end of every turn, secret blocking |
| `.claude/skills/` | The commands: `/setup`, `/spec`, `/slice`, `/codex-review`, `/eval`, `/wrapup` |
| `.claude/agents/test-writer.md` | A helper that writes tests from the spec without seeing the code |
| `docs/` | Spec, plan, decisions, eval results, AI workflow log and saved reviews |
| `src/app/llm.py` | The one place all LLM calls go: prompts from files, validated JSON output, one retry, call log without content |
| `evals/` | A small harness that scores the system on labelled examples |
| `.github/workflows/ci.yml` | On every push: formatting, lint, tests, eval, secret scan |

## Start here
1. **Once:** [docs/kit/SETUP.md](docs/kit/SETUP.md): install the tools and sign in (about 20 minutes).
2. **Each project:** [docs/kit/HOW_TO_USE.md](docs/kit/HOW_TO_USE.md): the case-day flow, step by step.

## Check the kit works
```bash
uv sync
uv run pytest
uv run python -m evals.run
```
