# Review 08: slice 9

- Date: 2026-11-22
- Mode: code (slice 9 only: `git diff 1140feb..HEAD`; the `reviewed` branch still sits before slice 8, whose review 07 was Claude's own)
- Model: gpt-6.2-astra
- Reasoning effort: high

**P1 — must fix**

- Two rejected notices identify individual homes and disclose disability-related adaptations. One description also specifies the residents’ care arrangements. Both addresses appear in titles, and one is repeated with a full postcode in its description. Redact the identifying locations and household details from the committed copy, then update D40 to record those edits. [First notice, line 13321](examples/runs/2026-11-16_2026-11-21.json:13321) · [Second notice, line 13628](examples/runs/2026-11-16_2026-11-21.json:13628)

**P2 — should fix**

- The README combines two different 9–15 Nov runs. The earlier run made 62 fresh extractions, cost $0.29 and shortlisted **eight**. The committed rerun used 122 cached extractions, made seven rationale calls, cost $0.006082 and shortlisted **seven**. Label the two runs separately so the README agrees with what the demo shows. [README.md, line 91](README.md:91)
- The 16–21 Nov total of about 16 minutes is accurate, but the reported five-minute fetch and eleven-minute extraction split disagrees with the timestamps. The raw notices were saved about 3m42s after startup, and the 125 logged extraction calls alone took 12m23s. Correct the split in the README and workflow log, or give just the verified total. [README.md, line 32](README.md:32) · [AI_WORKFLOW.md, line 47](docs/AI_WORKFLOW.md:47)
- The demo promises that nothing on the call needs an LLM, but the four live Claude Desktop answers still require Claude. The saved HTML and local MCP server work independently of the screening provider. Make the offline fallback explicit: open the pre-rendered page and use the written answers if Claude is unavailable. [DEMO.md, line 3](docs/DEMO.md:3)
- The rehearsal cites `output/report.md` for every answer, but that report gives only the region rejection for 109921. Its gated lot score of 0.75, its TUPE flag, and the flags on the other rejected notices are in the run JSON. Cite the JSON for those answers and the profile values, and the MCP tool description for the hard-gate rules. [DEMO.md, line 14](docs/DEMO.md:14) · [mcp_server.py, line 208](src/app/mcp_server.py:208)
- The plan records the approved Monday–Saturday exception, then still instructs the presenter to run 16–22 Nov with the default CLI. Following that step on the 23rd would start a paid run for different dates. Mark that step as superseded by D40 and cross-reference the exception in the spec’s full-week demo assumption. Keep the timed Desktop rehearsal open. [PLAN.md, line 99](docs/PLAN.md:99) · [SPEC.md, line 59](docs/SPEC.md:59)

**P3 — nice to have**

- The Desktop setup fallback says to run `where uv` on Windows. In PowerShell, `where` resolves to `Where-Object` and returns no path here. Use `where.exe uv`, which returned the executable path. [README.md, line 47](README.md:47)

I verified the new run’s 489 tender notices, 125 assessed, eight shortlisted, 117 rejected, rejection breakdown, scores, and $0.6141 cost. All six TUPE flags belong to rejected notices. The three documented name replacements are present, and I found no additional unmasked contact name, email address or phone number.

Both existing dated HTML pages contain the expected shortlists, and the older fallback run contains the documented Newcastle rejection. The MCP fallback test exercises a real stdio subprocess. I could inspect those artifacts and code paths, but `uv` could not initialize its cache in this read-only environment, so I could not independently rerun the renderer or confirm the reported 560 passing tests.

**Overall verdict — Hold the public demo copy until both household disclosures are redacted, then complete the timed Claude Desktop rehearsal.**
