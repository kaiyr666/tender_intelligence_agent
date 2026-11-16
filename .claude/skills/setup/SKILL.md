---
name: setup
description: First-time setup of a project created from this kit. Use when the user types /setup or says the project has just been cloned.
disable-model-invocation: true
---

Set up this project so the user can start building. Explain each step in one plain sentence; the user is not deeply technical.

1. Check the tools are installed: run `uv --version`, `git --version` and `codex login status`. If one is missing, stop and point the user to `docs/kit/SETUP.md` for that tool.
2. Run `uv sync` to install the Python dependencies.
3. If `.env` does not exist, run `cp .env.example .env`. Then tell the user: "Open `.env` in your editor and paste your API key after `ANTHROPIC_API_KEY=` (or the OpenAI one). I deliberately can't see that file." Never read or print `.env` yourself.
4. Create the review baseline so Codex can later review only new work: run `git branch -f reviewed HEAD`.
5. Run `uv run pytest -q` and `uv run ruff check .`. Both should pass on a fresh kit.
6. Check GitHub is connected: `git remote -v` must show the project's GitHub URL, and `git push` must succeed. If the push asks for a password or fails, stop and point the user to section 2 of `docs/kit/SETUP.md` (GitHub sign-in).
7. Report: what is ready, anything that failed and how to fix it, and the next step: "Paste the brief and run `/spec`."
