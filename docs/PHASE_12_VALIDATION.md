# Phase 12 validation checklist

Unchecked items have not passed. Integrated checks require Phases 8–10.

- [ ] F5 launch; light/dark themes, keyboard navigation, empty states and long summaries.
- [ ] No workspace, untrusted workspace, missing Python and unregistered project errors.
- [ ] Multi-root isolation; match event IDs and verification with CLI/MCP using the same database.
- [ ] Inspect evidence, navigate files, search with/without Ollama, capture Git, index and create an unconfirmed checkpoint.
- [ ] Disconnect mid-request, change workspace, restart/reconnect; no stale results or lost records.
- [ ] On target Mac M1 8GB: automatic saves/commits, failing test, fix, passing test, pause/resume and sensitive-path exclusion.
- [ ] Restart observer/model/editor; index queue recovers without duplicates.
- [x] Physically disconnect networking; repeat search, cited chat and fresh MCP retrieval. The CLI/MCP path passed on 2026-10-10; see the recorded trial below.
- [ ] Evaluate citations, dates, missing rationale, retrieval misses and false completion claims.
- [ ] Record backup offline demo.

| Measurement | Observed result |
|---|---|
| Observer idle CPU/RAM | Not measured |
| Model cold-start/RAM/swap | Not measured |
| Search/chat latency | First warm offline trial: semantic CLI search 143.1 ms, cited chat 4,842.0 ms, fresh MCP 1,518.1 ms. Phase 10 offline run: deterministic questions 174–546 ms, model-selected handoff 15,274.5 ms, named rationale 5,278.9 ms. These are end-to-end single-run timings, not a benchmark. |
| Missed/duplicate events | Not measured |
| Queue recovery and SQLite size | Not measured |
| Citation/date accuracy and retrieval misses | Not measured |

Record machine, date and measurement method alongside results. Phase 12 passes only after the integrated offline workflow succeeds on the target machine within agreed measured resource budgets.

## Physical offline trial — 2026-10-10

At 01:34 Manila time on the M1 Mac with 8 GB unified memory (macOS 26.6.2), Wi-Fi `en0` was turned off. The [saved report](phase12-offline-report.json) records `Wi-Fi Power (en0): Off` and a failed external TCP connection to `1.1.1.1:443`. Against the real `.arc/arc.sqlite3` database, `scripts.verify_offline_ai` returned a semantic rank-1 hit for `arc:event/8fbf5d9e14ac4ebba2c2163a97c685d1`, local `qwen3:1.7b` chat cited that event, and a fresh stdio MCP session returned a source-linked handoff and resolved the same event. The test process exited successfully. Wi-Fi was restored to `On` afterward and the default route returned on `en0`.

The validator command, run while Wi-Fi was off, was:

```bash
.venv/bin/python -m scripts.verify_offline_ai \
  --project "$PWD" --db "$PWD/.arc/arc.sqlite3" \
  --event 8fbf5d9e14ac4ebba2c2163a97c685d1 \
  --query 'Why did we use a local browser dashboard instead of another service?' \
  --report "$PWD/.arc/offline-physical-report.json" --require-wifi-off
```

This closes the specific physical network-off search/chat/MCP check. It did not exercise VS Code, a full observer/test workflow while offline, or an on-camera offline demo; those checks remain open above.

## Phase 10 offline question trial — 2026-10-10

The [Phase 10 report](phase10-offline-report.json) records a second physical Wi-Fi-off run on the same M1 8 GB Mac at 01:55 Manila time. External TCP was unreachable. The six planned questions and a named dashboard-rationale question ran against the real A.R.C. database; every returned citation resolved to its project event. The unnamed “this feature” rationale question returned no citation, and the error/fix question did not claim an unrecorded fix. The timeline exposed older history through `next_offset` and a stable snapshot. Wi-Fi was restored afterward. This targeted run supports Phase 10; it does not replace the open extension-host, full workflow, accuracy calibration, or resource measurements above.
