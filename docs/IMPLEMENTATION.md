# Current implementation notes

The full vision and roadmap remain in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). The current build integrates the CLI/MCP evidence store with opt-in observation, automatic indexing, timeline queries, cited evidence answers, and a VS Code extension. The older developer split below is historical planning; use [Phase 12 validation](PHASE_12_VALIDATION.md) for current acceptance status.

## Phase 11 integration

`arc/observer.py` provides explicit enable/pause/resume/disable controls and a polling worker. SQLite stores its baseline and commit cursor in `observer_state`. Concurrent collectors compare their cursors under a short write transaction, so one observation wins. Restart catches up reachable commits in batches of up to 100. Commit events use the original UTC commit time; `details.observed_at` records recovery time. Paused and disabled intervals are discarded when observation resumes. File bodies are hashed only for eligible paths and are never persisted; transient edits between five-second polls can be missed.

An active observer embeds at most two summaries per retry. Unindexed events in SQLite are its durable queue; model failures leave them pending. A time-limited `model_lease` serializes embedding and chat calls across processes sharing one database. A killed process's lease expires after 90 seconds.

`arc/chat.py` routes local **today/yesterday**, explicit `YYYY-MM-DD` ranges, named tasks, recorded errors and resolutions, rationale, handoff, and timeline questions through bounded project-scoped retrieval. The CLI uses the machine's current UTC offset unless `--timezone-offset` is supplied; the extension sends its offset. `all-minilm` handles semantic retrieval. Local `qwen3:1.7b` can write an introductory answer from at most 12 retrieved event summaries and return source IDs; A.R.C. validates the IDs and also returns deterministic evidence lines. Unknown IDs or model errors fall back to recorded evidence. Evidence lines label claims as unverified, passing tests as current or historical, and resolutions as reported rather than proved. Model prose can still add unsupported details despite a valid citation, as the [Phase 11/12 trial](phase11-12-validation-report.json) shows. The model unloads after every request. Historical daylight-saving timezone rules are not implemented.

Chat timeline pages contain at most 12 history entries. Repeated Git watcher events are grouped by local day in chat only, with the latest event cited as a representative; the raw SQLite/CLI timeline still has every event. The answer also shows per-day counts and up to four earlier source-linked milestones. `snapshot_rowid` keeps continuation stable if new events arrive; pass it back as CLI `--snapshot` or through the extension's **Load older history** button. See the [focused offline Phase 10 report](phase10-offline-report.json) for the real-model result and scope.

The extension supervises a project worker, reports observer/index state, runs configured tests, filters timelines, and opens cited evidence. Consent for connecting and collecting is separate. Windows cancellation terminates the virtual-environment process tree. Generation checks suppress replies from a disconnected project. Reopening an approved single-folder workspace restores the selection; explicit disconnect clears it. Activation tests mock VS Code; they do not certify appearance or keyboard behavior.

Fingerprint calculation now excludes sensitive/generated paths before hashing. Existing test fingerprints or checkpoints from the old algorithm may become stale; rerun tests or create a new checkpoint to obtain current evidence. No old events are deleted.


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

Browser on 127.0.0.1 ──> dashboard HTTP routes ──> the same ArcService and SQLite file
```

The first integrated contract is `ArcService` in `arc/service.py`. It accepts an explicitly registered `Path` for each operation. `arc/contracts.py` defines `GitSnapshot` and `SearchHit`. The memory engine receives a `Store` and an `Embedder` protocol, so retrieval can be evaluated without changing project collection or MCP tools. `MemoryEngine.index_pending(project_id)` writes vectors keyed by event ID. `MemoryEngine.search(project_id, query)` supports project and event-type scoping, semantic-only and keyword-only queries, and opt-in hybrid ranking. It returns `{mode, hits}` plus indexed/pending counts and labels keyword fallback explicitly. The `SearchHit` shape and default cosine scoring are unchanged.

Search indexes a Unicode- and whitespace-normalized copy of each summary; it does not rewrite the recorded evidence. Default search reports cosine-ranked embeddings and falls back to FTS5 if the local model or index is unavailable. `--semantic-only` requires the local model and reports a notice if records need indexing. `--keyword-only` reports keyword rank scores. `--hybrid` combines cosine and FTS5 ranks with reciprocal rank fusion; its score is a rank-fusion value, not a probability. Responses include `score_kind` so consumers can interpret each mode. Manual indexing remains available alongside the opt-in worker.

SQLite tables are `projects`, `sessions`, `tasks`, `events`, `incidents`, `incident_links`, `vectors`, `checkpoints`, `project_controls`, `observer_state`, and `event_fts`. Events include type, timestamp, source, source reference, optional task ID, optional session ID, Git head, fingerprint, JSON details, and an optional deduplication key enforced by a partial unique index. Incident rows identify their original error and explicitly recorded cause; links connect attempts, a reported resolution, and optional tests to their source events. Vectors store only selected event summaries; there is no source-file embedding. `project_controls` persists a project-scoped recording pause; `observer_state` persists the observation opt-in, pause flag, commit cursor, and worker pid. The database runs in WAL mode with a busy timeout so the watcher and CLI/MCP can share the file. A.R.C. stores its SQLite file with mode `0600` on macOS. Opening an older Phase 0 database adds the nullable session ID column without assigning old events to a session, adds the nullable `dedup_key` column, and creates later tables without rewriting old events.

`arc session start`, `status`, `list`, `show`, and `end` manage one explicit active session per project. New notes, Git captures, test results, and confirmation events join that session while it is active. `arc state` exposes the active session and session IDs on recent events; `arc_get_session_history` exposes its records to MCP clients. Events recorded outside a session retain a null session ID. This does not start observation automatically.

Every search hit has an event ID and source reference (`arc:event/<id>` or `git:commit/<hash>`). `arc event <id>` or the `arc_get_event` MCP tool retrieves that recorded evidence for inspection. `arc_get_timeline` exposes filtered, stable history pages.

`ArcService.project_handoff()` reads the current Git fingerprint, task states, latest session (active or ended), and the newest 1,000 project events. `arc/handoff.py` ranks recorded decisions, errors/failed tests, attempts, reported resolutions, corrections, and progress, reserves room for important categories where available, and deduplicates repeated summaries. The response bounds task and evidence lists, reports total counts and whether its event window was truncated, and gives each selected item an `arc:event/<id>` reference and selection reason. A test or confirmation counts as current progress only at the present fingerprint; evidence invalidated by a task correction is excluded. The suggested next task is derived from verification state and recent activity and is labelled as a suggestion. This is deterministic selection over recorded evidence, not an LLM-generated narrative or automatic activity capture; it works without Ollama or indexing.

`ArcService.open_incident()` starts from a project-scoped error event. Attempts record explicit `failed`, `inconclusive`, or `helped` outcomes; `link_incident_attempt()` can attach an existing attempt note. `resolve_incident()` stores an explicitly reported resolution and can attach a configured test only if it passed after the error at the current Git fingerprint. `incident_history()` labels that test current or historical as the project changes. A cause added at opening or resolution has its own source event. `search_incidents()` retrieves indexed error summaries through the local `all-minilm` engine, filters semantic scores below 0.55, and separates different explicitly recorded causes. A conservative keyword fallback requires two distinctive shared tokens. Results are always candidates, not confirmed diagnoses; the cutoff was checked on a small fixture and needs broader calibration.

`arc/dashboard.py` serves a bundled vanilla JavaScript/CSS interface on `127.0.0.1` using Python's standard library. The UI reads the same service methods as CLI/MCP for project handoffs, source-linked search, task review, event timeline, checkpoints, and incidents. It never treats a claim or a retrieved incident as verified completion or diagnosis. Static assets are installed as package data. The browser uses DOM `textContent` to display recorded strings, and mutating HTTP routes require a per-server request token. The server checks the loopback Host header, sets a restrictive content policy, and does not expose CORS. The local model check runs only when requested; normal page loads do not start Ollama. The dashboard runs while its foreground `arc dashboard` terminal is open; it is not a watcher or background service.

`arc/observer.py` is the Phase 8/11 opt-in worker, run by `arc watch` for the explicitly registered project — either in the foreground, detached via `arc observer start` (pid tracked in `observer_state.worker_pid`), or supervised by the VS Code extension. It polls Git state (head + fingerprint of eligible paths) at a low interval, records one `git` event per fingerprint change plus one `observer_commit` event per recovered commit, and skips generated directories and the sensitive-path list before hashing — file contents are never stored. A persisted `observer_state` commit cursor recovers commits made while no worker ran (`git rev-list` when the cursor is an ancestor; a non-fast-forward HEAD move is treated as a baseline change, not as fake commits). Pausing suspends collection; resume or disable re-establishes the baseline so deliberately unrecorded activity is not imported. `arc observer status|pause|resume|disable|stop` and the MCP tool `arc_get_observation_status` expose the state. An observed event carries `task_id NULL`; it can never mark a task tested or confirmed.

The pause control rejects new service-level notes, tasks, sessions, captures, tests, corrections, confirmations, incidents, and checkpoints for that project. Reading, ending an already active session, and indexing existing events remain possible. Memory deletion requires typing `DELETE <project name>` and removes that project's A.R.C. events, FTS rows, vectors, tasks, incidents, sessions, checkpoints, and pause setting in a transaction. Registration and source files remain. These controls affect the selected SQLite database only; set `ARC_DB` carefully before opening the dashboard.

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

**Implementation:** Phase 6 dashboard views and local privacy controls are implemented. The unfamiliar-user completion trial and broader incident evaluation remain in Phase 7. The Phase 8 opt-in watcher (`arc watch`, `arc observer`) is implemented and supervised by the Phase 11 VS Code extension; Phase 12 validation gates in PHASE_12_VALIDATION.md remain open. The Phase 13 zero-friction lifecycle (`arc workspace open|touch|close`, shared automatic sessions, crash recovery, sidebar handoff) is implemented and covered by automated tests; real VS Code host verification remains open. Preserve evidence semantics, `arc/contracts.py` shapes, and existing MCP tool behavior while extending them.

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
| File watcher | Implemented: `arc watch`/`arc observer` with deduplication, commit cursor recovery, sensitive-path filtering, and pause/resume baselines; covered by automated tests |
| Phase 6 browser dashboard | Implemented and covered by two HTTP tests for project views, source evidence, authorization, pause, and scoped deletion; unfamiliar-user browser trial remains open |
| Phase 3 task correction and verification review | Passed: service/MCP tests and installed CLI run in a temporary Git project; 16 automated tests passed on 2026-10-09 |
| Phase 4 handoff selector and CLI/MCP tool | Passed: 18 automated tests; installed `arc handoff` smoke test in a temporary Git project returned an unfinished task plus decision/failure/attempt references |
| Phase 4 fresh Codex retrieval | Passed for the real database: an ephemeral read-only session called `arc_get_project_handoff` and returned task `ccd44503aac9` with Git/test and decision/failure/attempt references. The developer later confirmed it at that Git fingerprint; the event remains historical after subsequent changes |
| Phase 5 linked incident search | Passed: 22 automated tests, including a live `all-minilm` paraphrase, different-cause separation, unrelated-query rejection, and stdio MCP calls. Installed CLI smoke test created and searched a linked incident in a temporary Git project |

These are narrow checks of the current prototype, not claims that the full product or hackathon evaluation is complete.

## Phase 2 retrieval check

Run `python -m scripts.evaluate_retrieval` with the local Ollama model available. The fixed synthetic set has seven events and five paraphrased questions. On 2026-10-09, the warm local model returned the expected event first for **4/5 semantic** and **4/5 hybrid** queries; FTS5 keyword search returned **1/5** first. Semantic and hybrid recall within three results was **5/5**. Median per-query latency in this small run was about 17 ms for semantic/hybrid search. The dependency-install question returned the related cache attempt first and the expected build failure second. An unrelated cooking question still returned a low-scoring candidate (cosine 0.131), so the engine must not treat every returned hit as a confirmed match. This is a small fixture, not a production accuracy claim. The user reported a separate successful disconnected-network semantic search on 2026-10-09; its terminal output remains to be captured for the demo evidence log.

The separate `first-test.sqlite3` database was indexed after the user's recorded session: three events indexed, and semantic, keyword, and hybrid search each retrieved its migration-error event with the same source reference. A direct MCP client call also retrieved that event using the new hybrid filter arguments.
