# Current implementation notes

The full vision and 14-day roadmap remain in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). This file describes the Phase 0 prototype plus the first explicit session-tracking step from Phase 1, so neither developer needs to infer a feature from the proposal.

## Current architecture

```text
Explicit CLI action ──> ArcService ──> Git snapshot / configured test
                           │                    │
                           └────────> SQLite projects, tasks, events, vectors, checkpoints
                                                   │
                                     MemoryEngine + local Ollama /api/embed
                                                   │
                                      Search hits with source references
                                                   │
                                          stdio MCP tools for Codex
```

The first integrated contract is `ArcService` in `arc/service.py`. It accepts an explicitly registered `Path` for each operation. `arc/contracts.py` defines `GitSnapshot` and `SearchHit`. The memory engine receives a `Store` and an `Embedder` protocol, so Developer 1 can evaluate models without changing project collection or MCP tools. `MemoryEngine.index_pending(project_id)` writes vectors keyed by event ID. `MemoryEngine.search(project_id, query)` returns `{mode, hits}` and labels keyword fallback explicitly.

SQLite tables are `projects`, `sessions`, `tasks`, `events`, `vectors`, `checkpoints`, and `event_fts`. Events include type, timestamp, source, source reference, optional task ID, optional session ID, Git head, fingerprint, and JSON details. Vectors store only selected event summaries; there is no source-file embedding. A.R.C. stores its SQLite file with mode `0600` on macOS. Opening an older Phase 0 database adds the nullable session ID column without assigning old events to a session.

`arc session start`, `status`, `list`, `show`, and `end` manage one explicit active session per project. New notes, Git captures, test results, and confirmation events join that session while it is active. `arc state` exposes the active session and session IDs on recent events; `arc_get_session_history` exposes its records to MCP clients. Events recorded outside a session retain a null session ID. This does not start observation automatically.

Every search hit has an `arc:event/<id>` source reference. `arc event <id>` or the `arc_get_event` MCP tool retrieves that recorded evidence for inspection.

## Evidence semantics

- A task claim is an explicit event and remains unverified.
- A Git observation linked to a task records visible changed paths and a fingerprint. It supports **implementation observed**, never feature correctness.
- A configured test linked to a task records its exit code and the project fingerprint before and after the run. A changed project or nonzero exit does not count as a current passing test.
- **Tests passed** means the named configured command passed at the current fingerprint. It does not prove the whole feature works.
- **Completed/confirmed** requires the prior evidence and an explicit CLI confirmation. Confirmation is timestamped as another event. The displayed state falls back when the project fingerprint changes.
- A checkpoint is an unconfirmed candidate. The state response marks it stale once the current fingerprint differs.

No raw source content is stored or uploaded. Explicit notes and captured test-output tails are redacted for common secret patterns, but the redactor is limited; do not record credentials. Git path filtering excludes common secret and database filenames. MCP responses are scoped to the configured project. Tools do not run tests or shell commands on an agent's request.

## Two parallel tracks from this baseline

**Developer 1:** Improve `arc/memory.py`. Create a small labelled incident fixture set and compare semantic search with FTS5 keyword search. Check paraphrase recall, false matches, latency, and offline behavior. Keep the `Embedder` and `MemoryEngine` method signatures stable.

**Developer 2:** Improve collection and product flow in `arc/git_evidence.py`, `arc/store.py`, `arc/service.py`, `arc/cli.py`, and `arc/mcp_server.py`. The next step is a permissioned file watcher and a simple dashboard showing events, task evidence, and handoffs. Keep recorded facts separate from agent statements. Keep MCP tool names and result fields stable.

**Shared checkpoint:** Run the same real repository through `init`, `task add`, `capture`, `test`, `index`, `search`, `checkpoint`, and MCP retrieval. Note actual results. Agree before changing `arc/contracts.py` or the SQLite schema.

## Phase 0 validation status

| Check | Status on this machine |
|---|---|
| Python 3.11 and package installation | Passed |
| SQLite evidence store and Git snapshot | Passed in automated tests |
| Claim is not marked tested without evidence | Passed in automated test |
| Tests and checkpoints become stale after project change | Passed in automated tests |
| MCP client initializes and calls `arc_get_project_state` over stdio | Passed in automated test |
| Explicit session grouping, MCP session history, and old-database migration | Passed in automated tests |
| Local `all-minilm` generates an embedding | Passed; 384 values returned |
| Paraphrased incident ranks above unrelated note | Passed in local model test and CLI smoke test; also passed with Ollama cloud features disabled |
| Network physically disconnected during search | Not yet tested |
| Codex configured in a fresh session | Not yet tested |
| File watcher and dashboard | Not implemented yet |

These results are narrow checks of this Phase 0 slice, not claims that the full product or hackathon evaluation is complete.
