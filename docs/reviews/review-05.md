# Review 05

- **Date:** 2026-11-22
- **Mode:** changes since the last review (`reviewed..HEAD`, 2763169..983fd40: the demo plan and slice 6). Run as `codex exec --sandbox read-only` with the diff named in the prompt, because Codex 0.169 refuses `review --base` together with a prompt.
- **Model:** gpt-6.2-astra, reasoning effort high (69k tokens), read-only and static: it could not run the tests

## P1 — must fix

1. **A budget-stopped run is saved as complete.** The fixture has `complete: true` and `problem: null` even though one notice was skipped for lack of budget. The Markdown report marks that same run **INCOMPLETE**, so slice 7’s `list_runs` would report the wrong health. Save overall completion as false when the fetch stops or any notice is `not processed`, preserve both reasons when they coincide, and test the saved status against the report banner. [runs.py:154](src/app/runs.py:154) · [fixture:356](tests/fixtures/runs/2026-11-09_2026-11-15.json:356)

2. **Importing the run reader loads the extraction and LLM pipeline.** `runs.py` imports `report` and `score` at module load. `score` imports `extract`, which imports `llm`, whose configuration calls `load_dotenv()`. Both planned readers therefore load `.env` merely to open a saved file, contrary to the slice 7–8 isolation rule. Move producer-only imports into `to_record` or behind `TYPE_CHECKING`, and put the shared output path somewhere that can be imported independently. Add a fresh-process test that loads the fixture and checks that `app.extract` and `app.llm` stay unloaded. [runs.py:17](src/app/runs.py:17) · [PLAN.md:45](docs/PLAN.md:45)

3. **The saved profile cannot supply slice 7’s `get_profile` response.** The snapshot keeps service names but drops each service’s `includes` and `excludes`. Slice 7 promises those definitions and directs the server to read the *current* TOML, which conflicts with D37 and can give an assistant the wrong explanation for an older run. Store the definitions in the snapshot, make `get_profile` use the selected run with the newest as default, and update the plan and both JSON files together. [runs.py:77](src/app/runs.py:77) · [PLAN.md:72](docs/PLAN.md:72)

## P2 — should fix

1. **An interrupted rerun can destroy the previous valid record.** `write_text` truncates the week’s file before the replacement is fully written, so an MCP reader can also encounter partial JSON during a normal rerun. Write a temporary file in the same directory, close it, then replace the destination atomically. Test that a failed replacement leaves the old run readable. [runs.py:167](src/app/runs.py:167)

2. **A misnamed run can be selected as the wrong week.** `list_runs` orders files by filename, while `load_run` checks the embedded ID only against the embedded dates. A valid older record copied under a newer week’s filename therefore wins the default selection. When discovering files in a runs directory, require the canonical filename stem to match the validated `run_id`. Also apply the existing date-order check to the record itself. [runs.py:109](src/app/runs.py:109) · [runs.py:195](src/app/runs.py:195)

3. **Malformed files can put untrusted content into reader diagnostics.** The version error interpolates the raw `schema_version` value, including arbitrary text or an object. Other validation failures retain the original Pydantic exception as their cause, so a traceback can still print rejected input. Report the version number only when it is an integer, suppress the input-bearing exception chain, and test the formatted traceback with a distinctive marker. [runs.py:182](src/app/runs.py:182) · [runs.py:188](src/app/runs.py:188)

**Verification.** All 122 example notices matched the local CSV by ID, outcome, rank and reason. The seven shortlist ranks were consecutive, and every saved best-lot ID resolved. The content scan found no email addresses or key-pattern matches. The phone-pattern matches were procurement IDs inside URLs. Pytest and Ruff could not run in this environment because the virtual environment’s Python was unavailable and Ruff execution was denied. CI status was unverified.

**Overall verdict — Fix run health, reader isolation, and the profile contract before building slices 7 and 8 on schema v1.**
