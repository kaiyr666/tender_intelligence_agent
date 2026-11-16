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
