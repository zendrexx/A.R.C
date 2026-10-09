# Current implementation notes

The full vision and phase roadmap remain in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). This file describes the current Phases 0–5 CLI/MCP prototype. One developer owns implementation; the teammate owns documentation, test records, and video promotion.

## Current architecture

```text
Explicit CLI action ──> ArcService ──> Git snapshot / configured test
                           │                    │
                           └────────> SQLite projects, tasks, events, incidents, links,
                                      vectors, checkpoints
                                                   │
                                     MemoryEngine + local Ollama /api/embed
                                                   │
                                      Search hits with source references
                                                   │
                                          stdio MCP tools for Codex

Recorded events + current task evidence ──> bounded handoff selector
                                              └──> arc handoff / read-only MCP tool

Error event ──> incident ──> linked attempt outcomes / reported resolution / test
                            └──> local error retrieval + explicit cause separation
```

The first integrated contract is `ArcService` in `arc/service.py`. It accepts an explicitly registered `Path` for each operation. `arc/contracts.py` defines `GitSnapshot` and `SearchHit`. The memory engine receives a `Store` and an `Embedder` protocol, so retrieval can be evaluated without changing project collection or MCP tools. `MemoryEngine.index_pending(project_id)` writes vectors keyed by event ID. `MemoryEngine.search(project_id, query)` supports project and event-type scoping, semantic-only and keyword-only queries, and opt-in hybrid ranking. It returns `{mode, hits}` plus indexed/pending counts and labels keyword fallback explicitly. The `SearchHit` shape and default cosine scoring are unchanged.

Search indexes a Unicode- and whitespace-normalized copy of each summary; it does not rewrite the recorded evidence. Default search reports cosine-ranked embeddings and falls back to FTS5 if the local model or index is unavailable. `--semantic-only` requires the local model and reports a notice if records need indexing. `--keyword-only` reports keyword rank scores. `--hybrid` combines cosine and FTS5 ranks with reciprocal rank fusion; its score is a rank-fusion value, not a probability. Responses include `score_kind` so consumers can interpret each mode. Indexing is still explicit in this phase.

SQLite tables are `projects`, `sessions`, `tasks`, `events`, `incidents`, `incident_links`, `vectors`, `checkpoints`, and `event_fts`. Events include type, timestamp, source, source reference, optional task ID, optional session ID, Git head, fingerprint, and JSON details. Incident rows identify their original error and explicitly recorded cause; links connect attempts, a reported resolution, and optional tests to their source events. Vectors store only selected event summaries; there is no source-file embedding. A.R.C. stores its SQLite file with mode `0600` on macOS. Opening an older Phase 0 database adds the nullable session ID column without assigning old events to a session, and creates the Phase 5 tables without rewriting old events.

`arc session start`, `status`, `list`, `show`, and `end` manage one explicit active session per project. New notes, Git captures, test results, and confirmation events join that session while it is active. `arc state` exposes the active session and session IDs on recent events; `arc_get_session_history` exposes its records to MCP clients. Events recorded outside a session retain a null session ID. This does not start observation automatically.

Every search hit has an `arc:event/<id>` source reference. `arc event <id>` or the `arc_get_event` MCP tool retrieves that recorded evidence for inspection.

`ArcService.project_handoff()` reads the current Git fingerprint, task states, latest session (active or ended), and the newest 1,000 project events. `arc/handoff.py` ranks recorded decisions, errors/failed tests, attempts, reported resolutions, corrections, and progress, reserves room for important categories where available, and deduplicates repeated summaries. The response bounds task and evidence lists, reports total counts and whether its event window was truncated, and gives each selected item an `arc:event/<id>` reference and selection reason. A test or confirmation counts as current progress only at the present fingerprint; evidence invalidated by a task correction is excluded. The suggested next task is derived from verification state and recent activity and is labelled as a suggestion. This is deterministic selection over recorded evidence, not an LLM-generated narrative or automatic activity capture; it works without Ollama or indexing.

`ArcService.open_incident()` starts from a project-scoped error event. Attempts record explicit `failed`, `inconclusive`, or `helped` outcomes; `link_incident_attempt()` can attach an existing attempt note. `resolve_incident()` stores an explicitly reported resolution and can attach a configured test only if it passed after the error at the current Git fingerprint. `incident_history()` labels that test current or historical as the project changes. A cause added at opening or resolution has its own source event. `search_incidents()` retrieves indexed error summaries through the local `all-minilm` engine, filters semantic scores below 0.55, and separates different explicitly recorded causes. A conservative keyword fallback requires two distinctive shared tokens. Results are always candidates, not confirmed diagnoses; the cutoff was checked on a small fixture and needs broader calibration.

## Evidence semantics

- A task claim is an explicit event and remains unverified.
- A Git observation linked to a task records visible changed paths and a fingerprint. It supports **implementation observed**, never feature correctness.
- A configured test linked to a task records its exit code and the project fingerprint before and after the run. A changed project or nonzero exit does not count as a current passing test.
- **Tests passed** means the named configured command passed at the current fingerprint. It does not prove the whole feature works.
- **Completed/confirmed** requires the prior evidence and an explicit CLI confirmation. Confirmation is timestamped as another event. The displayed state falls back when the project fingerprint changes.
- A correction to `planned` invalidates earlier linked observations, tests, and confirmations. A correction to `implementation_observed` retains one existing linked Git observation but requires a new passing test and confirmation. Both are `task_correction` events with a reason and `arc:event/<id>` source reference. Repeating `arc capture` at the unchanged corrected fingerprint cannot undo a `planned` correction.
- `arc task review ID` and read-only MCP `arc_get_task_review` show the current Git fingerprint, evidence statuses, missing checks, and source references. A confirmation from an older fingerprint does not carry over when a new test passes on changed code.
- A checkpoint is an unconfirmed candidate. The state response marks it stale once the current fingerprint differs.

No raw source content is stored or uploaded. Explicit notes and captured test-output tails are redacted for common secret patterns, but the redactor is limited; do not record credentials. Git path filtering excludes common secret and database filenames. MCP responses are scoped to the configured project. Tools do not run tests or shell commands on an agent's request.

## Work from this baseline

**Implementation:** Phase 5's linked incident history and conservative candidate search are implemented, and its controlled local-model gate passed. Next, build Phase 6 interface views and expand incident evaluation in Phase 7. The permissioned watcher is future Phase 8. Preserve evidence semantics, `arc/contracts.py` shapes, and existing MCP tool behavior while extending them.

**Documentation and video:** Follow [DOCUMENTATION_AND_VIDEO.md](DOCUMENTATION_AND_VIDEO.md). Validate the README on a clean terminal, record exact commands/results, explain current limitations, and prepare the promotion and backup demo videos from real behavior.

**Integration checkpoint:** Run the same real repository through `init`, `task add`, `capture`, `test`, `index`, `search`, `checkpoint`, and MCP retrieval. Note actual results. See [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md) for current-use commands and implementation order.

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
| Network physically disconnected during semantic search | Passed by user report on 2026-10-09: networking off and `--semantic-only` returned semantic results; exact terminal output not yet saved in the evidence log |
| Codex configured in a fresh session | Passed per user confirmation on 2026-10-09; recorded session `0f5c0c8e905a` was retrieved through MCP |
| File watcher and dashboard | Not implemented yet |
| Phase 3 task correction and verification review | Passed: service/MCP tests and installed CLI run in a temporary Git project; 16 automated tests passed on 2026-10-09 |
| Phase 4 handoff selector and CLI/MCP tool | Passed: 18 automated tests; installed `arc handoff` smoke test in a temporary Git project returned an unfinished task plus decision/failure/attempt references |
| Phase 4 fresh Codex retrieval | Passed for the real database: an ephemeral read-only session called `arc_get_project_handoff` and returned task `ccd44503aac9` with Git/test and decision/failure/attempt references. The developer later confirmed it at that Git fingerprint; the event remains historical after subsequent changes |
| Phase 5 linked incident search | Passed: 22 automated tests, including a live `all-minilm` paraphrase, different-cause separation, unrelated-query rejection, and stdio MCP calls. Installed CLI smoke test created and searched a linked incident in a temporary Git project |

These are narrow checks of the current prototype, not claims that the full product or hackathon evaluation is complete.

## Phase 2 retrieval check

Run `python -m scripts.evaluate_retrieval` with the local Ollama model available. The fixed synthetic set has seven events and five paraphrased questions. On 2026-10-09, the warm local model returned the expected event first for **4/5 semantic** and **4/5 hybrid** queries; FTS5 keyword search returned **1/5** first. Semantic and hybrid recall within three results was **5/5**. Median per-query latency in this small run was about 17 ms for semantic/hybrid search. The dependency-install question returned the related cache attempt first and the expected build failure second. An unrelated cooking question still returned a low-scoring candidate (cosine 0.131), so the engine must not treat every returned hit as a confirmed match. This is a small fixture, not a production accuracy claim. The user reported a separate successful disconnected-network semantic search on 2026-10-09; its terminal output remains to be captured for the demo evidence log.

The separate `first-test.sqlite3` database was indexed after the user's recorded session: three events indexed, and semantic, keyword, and hybrid search each retrieved its migration-error event with the same source reference. A direct MCP client call also retrieved that event using the new hybrid filter arguments.
