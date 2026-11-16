# How to use the kit on case day

You set scope, approve and judge; Claude Code builds; Codex checks. Total attention needed from you: about 30 minutes of decisions across five hours.

## The flow

| Time | You type | What happens | What you do |
|---|---|---|---|
| 0:00 | `/spec` + paste the brief | Claude asks a few questions, then writes the spec and a plan of 3 to 5 slices | Answer the questions. **Read and edit `docs/SPEC.md` and `docs/PLAN.md`**: right problem? realistic scope? |
| 0:35 | `/codex-review plan` | Codex critiques the plan | Choose which points to act on |
| 0:45 | `/slice` | Claude builds one slice, tests it, commits, pushes to GitHub, stops | Look at the result (2 to 3 minutes). Say "next" or what to fix |
| … | `/slice` (repeat) | Same for each slice | Same. Type `/clear` between slices to give Claude a fresh start; the plan lives in files, so nothing is lost |
| 3:15 | `/eval` | Measures quality on labelled examples | Check the numbers make sense |
| 3:45 | `/codex-review` | Codex reviews the code since the last review | Decide what to fix now and what to list as a limitation |
| 4:15 | `/wrapup` | Final README, all checks, release tag | **Write "Where it breaks" and "Next steps" yourself** |
| 4:50 | — | Already pushed by `/wrapup` | Open the repo on GitHub and check the green tick |

## What runs automatically (you do nothing)
- **After every file edit:** code is formatted and lint-checked; Claude fixes problems immediately.
- **When Claude finishes a turn:** all tests run; if any fail, Claude has to fix them first.
- **Always:** Claude is blocked from reading your `.env` file or writing anything that looks like an API key.
- **After every slice:** the work is pushed to GitHub, so it is backed up and its history shows how the build progressed.
- **On every push to GitHub:** CI runs formatting, lint, tests, the eval and a secret scan.

## Good habits
- **Edit the spec, don't just approve it.** Fifteen minutes there saves an hour later.
- **If Claude asks a question, it is because the spec is unclear.** Answer it, and add the answer to the spec.
- **When you overrule the AI, say why.** It goes in `docs/AI_WORKFLOW.md`, and those are good stories for the debrief.
- **Running late?** Cut a slice rather than rushing all of them. Say so in the README.

## Commands
| Command | Use it to |
|---|---|
| `/setup` | Prepare a freshly cloned project |
| `/spec` | Turn the brief into a spec and plan |
| `/slice` | Build the next slice (or `/slice 3` for a specific one) |
| `/codex-review` | Independent review: `plan`, empty for new work, or `all` |
| `/eval` | Measure quality and update `docs/EVAL.md` |
| `/wrapup` | Final docs, checks and release tag |
| `/clear` | Start a fresh conversation (built into Claude Code) |
