# Phase 12 validation checklist

Unchecked items have not passed. Integrated checks require Phases 8–10.

- [ ] F5 launch; light/dark themes, keyboard navigation, empty states and long summaries.
- [ ] No workspace, untrusted workspace, missing Python and unregistered project errors.
- [ ] Multi-root isolation; match event IDs and verification with CLI/MCP using the same database.
- [ ] Inspect evidence, navigate files, search with/without Ollama, capture Git, index and create an unconfirmed checkpoint.
- [ ] Disconnect mid-request, change workspace, restart/reconnect; no stale results or lost records.
- [ ] On target Mac M1 8GB: automatic saves/commits, failing test, fix, passing test, pause/resume and sensitive-path exclusion.
- [ ] Restart observer/model/editor; index queue recovers without duplicates.
- [ ] Physically disconnect networking; repeat search, cited chat and fresh MCP retrieval.
- [ ] Evaluate citations, dates, missing rationale, retrieval misses and false completion claims.
- [ ] Record backup offline demo.

| Measurement | Observed result |
|---|---|
| Observer idle CPU/RAM | Not measured |
| Model cold-start/RAM/swap | Not measured |
| Search/chat latency | Not measured |
| Missed/duplicate events | Not measured |
| Queue recovery and SQLite size | Not measured |
| Citation/date accuracy and retrieval misses | Not measured |

Record machine, date and measurement method alongside results. Phase 12 passes only after the integrated offline workflow succeeds on the target machine within agreed measured resource budgets.
