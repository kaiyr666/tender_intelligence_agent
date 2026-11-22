# Review 06

- **Date:** 2026-11-22
- **Mode:** changes since the last review (`reviewed..HEAD`, 85e7d0a..9d07904: slice 7, the MCP server). Run as `codex exec --sandbox read-only` with the diff named in the prompt.
- **Model:** gpt-6.2-astra, reasoning effort high (55k tokens), read-only and static: it could not run the tests or Ruff

**P1 — must fix**

No P1 issues found in the slice 7 diff.

**P2 — should fix**

- The `get_profile` tool description omits the evidence rule for two hard gates, so an assistant can tell the bid team that an excluded primary service or missing mandatory accreditation automatically rejects a lot. State that both require a supporting quote found in the notice, and that an unsupported gate sends the lot for review unless another gate rejects it. [src/app/mcp_server.py:208](<C:/Users/админ/Desktop/AI Development/tender_intelligence_agent/src/app/mcp_server.py:208>)
- Every single-run lookup parses and retains every saved run, even when the caller supplies an exact `run_id`. The committed example is about 698 KB, so a year of comparable weekly runs would parse roughly 36 MB of JSON just to answer one profile question. Load only the named file for an explicit ID, stop at the first readable file for the newest run, and add a test that counts `load_run` calls. [src/app/mcp_server.py:256](<C:/Users/админ/Desktop/AI Development/tender_intelligence_agent/src/app/mcp_server.py:256>)
- The README says the harm from instructions planted in a notice is limited to a wrong answer, but the assistant reading that notice may have other tools that can write or send data. Describe the read-only guarantee as applying to this server and make clear that the client’s other permissions determine the possible effects. [README.md:125](<C:/Users/админ/Desktop/AI Development/tender_intelligence_agent/README.md:125>)

**P3 — nice to have**

- The connection guide says all five tools accept `run_id`, but `list_runs()` takes no arguments. Document `list_runs()` as the discovery call and say the other four tools default to the newest readable run. [README.md:36](<C:/Users/админ/Desktop/AI Development/tender_intelligence_agent/README.md:36>)

`git diff --check reviewed..HEAD` passed. I inspected the tests and committed example. The sandbox could not launch the project’s Python interpreter or Ruff, so I could not independently verify the reported test and lint results.

**Overall verdict — Slice 7 implements all five planned tools. Correct the gate guidance and security documentation, and make single-run lookups read only the records they need.**
