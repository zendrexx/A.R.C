# A.R.C. — Agent Recall & Continuity

A.R.C. is a local development-memory prototype. It records **selected** Git state, explicit notes, task claims, and configured test results in SQLite. A local Ollama embedding model makes those records searchable by meaning. A stdio MCP server lets a new Codex session request an evidence-backed project handoff.

The CLI and MCP evidence store now also supports opt-in Git observation, automatic indexing, paginated history, and cited local answers. The VS Code extension integrates these features. The [product plan](docs/DEVELOPMENT_PLAN.md) describes the broader vision; [Phase 12 validation](docs/PHASE_12_VALIDATION.md) records the remaining release gates.


One developer owns implementation; the teammate owns documentation, test records, and video promotion. Use the [project workflow](docs/PROJECT_WORKFLOW.md) for the current commands and implementation order, the [documentation/video checklist](docs/DOCUMENTATION_AND_VIDEO.md) for presentation work, and the [test evidence log](docs/TEST_RESULTS.md) for recorded results. A.R.C. reads local Git state; a Git push is needed only to share source or documentation between machines.

The [VS Code extension](extension/README.md) provides Memory and Chat views, project selection, observation controls, configured test execution, and source inspection. Answers quote recorded evidence; optional local `qwen3:1.7b` selects relevant sources. Free-form generated summaries are not implemented.

## Set up on macOS

Python 3.11, Git, and Ollama are required. The first package install and model pull need internet. In a terminal at the repository root:

```bash
brew install python@3.11 ollama
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev]'
arc --help
OLLAMA_NO_CLOUD=1 ollama serve
```

The regular package install avoids a macOS issue on this machine where Python skips the hidden `.pth` file created by an editable install. If you already installed with `pip install -e` and `arc` fails with `ModuleNotFoundError: No module named 'arc'`, run `python -m pip install --no-deps --force-reinstall .` in the active virtual environment, then retry `arc --help`. Reinstall after changing A.R.C. source code so the installed command uses the new code.

Leave Ollama running in that terminal. `OLLAMA_NO_CLOUD=1` disables Ollama cloud features; the local embedding model still runs on your computer. Open another terminal at the repository root:

```bash
source .venv/bin/activate
ollama pull all-minilm
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc init --test-command "$PWD/.venv/bin/python -m pytest -q"
arc state
```

`arc index` sends the selected event summaries only to Ollama on `127.0.0.1`. Default search keeps cosine-ranked semantic results and says `"mode": "semantic"`. If Ollama is unavailable or records have not been indexed, ordinary search labels its FTS5 results `keyword_fallback`; `--semantic-only` instead requires the model and reports when indexing is needed. An enabled observer indexes small batches automatically and retries pending records after model outages.

## Open the local dashboard

After the setup above, run this from the repository root:

```bash
source .venv/bin/activate
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc dashboard
```

The command opens `http://127.0.0.1:8765/` in your browser. Keep that terminal open; press `Ctrl+C` to stop the dashboard. If the browser does not open, copy the address printed by the command. Use `arc dashboard --no-browser --port 8766` if you want to open it yourself or port 8765 is occupied. The browser shows registered projects, source-linked handoff, search, task evidence, timeline, checkpoints, incidents, and local AI status. The Settings view can pause new manual records and permanently clear one project's A.R.C. memory after you type its exact confirmation phrase. Deletion keeps your source files and project registration.

The dashboard runs only on loopback and uses the same `ArcService` and SQLite database as the CLI and MCP server. It does not start sessions, run tests, watch files, or index new events on its own. Use `arc watch`, `arc capture`, `arc test`, and `arc index` to record and index development activity. The dashboard's **Index pending events** button runs the same local indexing operation. Its **Check local model** button tests `all-minilm` on your computer; the rest of the dashboard is usable without Ollama.

## Watch a project automatically

`arc watch` is an opt-in foreground worker for the selected registered project. Keep its terminal open while you work:

```bash
arc watch            # Ctrl+C to stop
arc observe status   # worker, cursor, and pause state from another terminal
arc observe pause    # suspend all new recording for this project
arc observe resume   # resume; anything changed while paused is not imported
arc observe stop     # turn the opt-in off; a running worker exits
```

While running, the worker records one `file_change` event per stable change (ten unchanged saves stay one record), and one `commit` event per new commit — including commits made while no worker was running, recovered through a persisted Git cursor. Generated directories and sensitive paths such as `.env` are skipped before anything is stored, and file contents are never recorded — only the path and a content hash. An observed event can never mark a task tested or confirmed; that still requires the explicit `arc capture`/`arc test`/`arc task confirm` evidence.

The setup commands register the real project database without adding sample incidents. For a separate example run, use the [first hands-on test](#first-hands-on-test). For actual development, start a session and follow [the current-use steps](docs/PROJECT_WORKFLOW.md#use-the-current-prototype).

Use `arc search "database upgrade" --kind error` to filter by event type. Use `--keyword-only` to search without Ollama, or `--hybrid` to combine semantic and exact keyword rankings. Results include indexed and pending record counts; `score_kind` identifies how each ranking score was computed, and scores are not probabilities.

## Record real project progress

Use `arc --project /absolute/path/to/repository ...` to select a different Git project. Registration is explicit. The configured test command is an executable plus arguments; A.R.C. never executes a command found in a note or agent response.

```bash
printf 'Task title: '
read -r task_title
task_id="$(arc task add "$task_title" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
printf 'Saved task ID: %s\n' "$task_id"
arc task review "$task_id"
```

After making a relevant code change, record and review its evidence:

```bash
arc capture --task "$task_id"
arc test --task "$task_id"
arc task review "$task_id"
arc handoff
```

A claim alone remains **planned**. A linked Git observation can raise it to **implementation observed**. A passing configured test at the current Git fingerprint raises it to **tests passed**. After reviewing the task, `arc task confirm "$task_id"` marks it **completed/confirmed**. If the project changes afterward, the earlier test is no longer shown as current evidence. `arc checkpoint` saves an **unconfirmed candidate** and reports when it becomes stale.

`arc task review "$task_id"` lists current requirements, missing checks, and source-linked evidence. If a task needs a downward correction, use `arc task correct "$task_id" --to planned --reason "Previous status was inaccurate"` or `--to implementation_observed --reason "The test needs repeating"`. The second choice requires a linked Git observation. Corrections invalidate earlier tests and confirmations; they cannot create a passing test or confirmation. A confirmation from an older Git fingerprint must be repeated after new code and a new passing test.

`arc capture` records changed paths and a Git fingerprint; it does not store source files or a Git diff. `arc test` stores the configured command, exit code, fingerprint, and a redacted tail of output. Avoid putting secrets in the configured command.

## First-class handoff and local incident workflows

`arc handoff` lists unfinished tasks, currently confirmed tasks, the latest session (even after it ends), and up to six selected source-linked events. Decisions, failures, attempts, and reported resolutions get priority; agent claims remain labelled unverified. `suggested_next_task` is a recommendation from recorded task state and recent activity, not an assertion about your intent. Use `arc handoff --limit 10` to show more selected events. This handoff reads SQLite and Git locally and does not require `arc index` or Ollama; it cannot recover work you have not recorded.

## Remember a debugging incident

Start with a real error note. The commands below save returned IDs so they can be reused without typing them manually:

```bash
error_id="$(arc note --kind error "SQLite migration failed because users table was missing" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
incident_id="$(arc incident open "$error_id" --cause "missing users table" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
arc incident attempt "$incident_id" "Checked the migration order" --outcome helped
# After an actual fix, record the configured test and report the resolution:
test_id="$(arc test | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
arc incident resolve "$incident_id" "Created users table before migration" --test-event "$test_id"
arc incident show "$incident_id"
arc index
arc incident search "Database upgrade crashed: missing users table during migration" --cause "missing users table"
```

Use `arc incident link-attempt INCIDENT_ID ATTEMPT_EVENT_ID --outcome failed` for a pre-existing attempt note, and `arc incident list` to inspect recorded incidents. A reported resolution is an explicit statement, not an automatic proof of a fix. A linked test must have passed after the error at the current Git fingerprint when attached; later changes mark it historical. Search returns **candidates**, separates explicitly different recorded causes, and rejects weak semantic matches. If the new cause is unknown, omit `--cause` and inspect the history before reusing an earlier resolution. New incident events need `arc index` before semantic search; without Ollama, a conservative keyword fallback remains available.

**No GitHub push is needed.** A.R.C. reads the local Git repository, including eligible uncommitted edits and untracked files. Manual commands remain available: `arc capture`, `arc test`, and `arc index`. Automatic observation requires an explicit opt-in and an active worker.

## Observe and ask locally

After registering the project, use the same database for CLI, extension, and MCP:

```bash
arc observer enable
arc observer-watch
```

The worker polls eligible Git state every five seconds, coalesces unchanged saves, records reachable commits made while it was stopped, and retries indexing two records at a time. It creates an observation session if no session is active. Sessions remain open across worker restarts; `arc session end` closes one explicitly. Run controls and queries from another terminal:

```bash
arc observer pause
arc observer resume
arc observer disable
arc timeline --kind test --since 2026-10-01 --until 2026-10-10
arc chat "Where did we leave off?" --keyword-only
arc chat "What happened yesterday?" --timezone-offset 480
```

Resume establishes a new baseline and discards paused activity. Re-enabling a disabled observer also begins at current state. Worker restart while still enabled recovers its persisted commit cursor. Edits made and reverted between polls can be missed. External terminal tests are not automatically verified: use the configured test command through CLI or the extension.

Chat returns inspectable event IDs and exact recorded summaries, including labels for unverified claims. `--keyword-only` avoids model requests. Otherwise retrieval uses local Ollama with labelled fallback, and optional `qwen3:1.7b` selects sources; install it with `ollama pull qwen3:1.7b`. Calendar words use the supplied UTC offset in minutes. History pages expose `next_offset`; queries never send the whole archive to chat. The chat model unloads after each request, and model calls sharing one database are serialized.


## First hands-on test

Use the existing A.R.C. repository with a separate test database so the example error does not enter your real project memory. In a terminal at its root, run:

```bash
source .venv/bin/activate
export ARC_DB="$PWD/.arc/first-test.sqlite3"
arc init --test-command "$PWD/.venv/bin/python -m pytest -q"
arc session start "First A.R.C. test"
arc note --kind error "SQLite migration failed because a table was missing"
arc capture
arc test
arc state
arc session list
```

Copy the `id` from `arc session start`, then run `arc session show SESSION_ID`. The note, Git capture, and test event should have that same `session_id`. `arc test` should report `"passed": true`; it runs the configured test command against the current local Git state. End with `arc session end`. Events recorded after that have a null session ID. Sessions group evidence; they do not capture activity automatically.

For semantic search, keep `OLLAMA_NO_CLOUD=1 ollama serve` running in another terminal, then run:

```bash
arc index
arc search "Why did the database upgrade break?" --semantic-only
```

The search result should say `"mode": "semantic"` and include the recorded migration error with an `arc:event/<id>` reference. The user reported on 2026-10-09 that this semantic search still worked with networking off. Save the exact command and result during a repeat run for presentation evidence. The fresh Codex MCP trial also succeeded on 2026-10-09.

## Connect to Codex

The MCP server is scoped to one registered project. Set `ARC_DB` to the database you want Codex to read (`first-test.sqlite3` for the trial or `arc.sqlite3` for normal use), then run this **once** from the repository root to add it to your local Codex configuration:

```bash
codex mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$ARC_DB" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
codex mcp list
```

If the terminal reports `codex: command not found`, use the bundled VS Code Codex binary and the real-database reconfiguration commands in [the project workflow](docs/PROJECT_WORKFLOW.md#make-codex-read-the-real-database). Changing `ARC_DB` in a terminal does not update an MCP entry that was already saved.

Restart the Codex session, then ask: **“Call A.R.C.'s `arc_get_project_handoff` and tell me what is unfinished, what is currently verified, and which source events support the handoff.”** For a new error, ask it to call `arc_search_incidents`, then `arc_get_incident` for the relevant source-linked history. The server also offers `arc_list_incidents`, `arc_get_project_state`, `arc_search_memory`, `arc_get_recent_changes`, `arc_get_task_history`, `arc_get_task_review`, `arc_get_session_history`, `arc_get_event`, and `arc_create_checkpoint`. The last tool saves an unconfirmed candidate. Connecting the server makes returned project summaries available to the coding agent, so review what you record before enabling it.

The [official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp) documents local stdio servers and `codex mcp add`. The server uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). Ollama's [all-minilm model page](https://ollama.com/library/all-minilm) documents the model pull and local embedding endpoint; its [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) documents local-only mode.

## Tests

```bash
python -m pytest -q
```

The tests cover unverified claims, auditable task correction, current versus stale tests and confirmations, handoff selection, incident links and cause separation, checkpoint freshness, privacy filtering, session grouping and migration, semantic ranking, keyword fallback, local dashboard routes and controls, and real stdio MCP client/server calls. Live-model tests run when local Ollama and `all-minilm` are available; otherwise they skip. Run `python -m scripts.evaluate_retrieval` for the fixed seven-record semantic-versus-keyword comparison. The user-reported disconnected-network result still needs captured terminal output for the hackathon evidence package.

For Phase 7's larger labelled incident check, run `python -m scripts.evaluate_incidents`. Its synthetic data stay in a temporary database. Read [the measured results and limits](docs/PHASE7_VALIDATION.md), use [the field-trial and recording runbook](docs/PHASE7_DEMO.md), and open [the local presentation deck](docs/PITCH_DECK.html) in a browser. These materials do not replace a recorded offline trial or an unfamiliar-user trial.

The runbook includes `python -m scripts.verify_phase7_journey` to repeat the real database's dashboard, semantic search, and checkpoint read path. It checks loopback use but does not turn off the Mac's network connection.

## Project roles and next gate

The implementation developer owns Python, SQLite, local retrieval, CLI, MCP, and future interface work. The teammate owns the setup walkthrough, test evidence log, presentation, and video. The shared technical flow is **recorded event → SQLite `events` row → embedding indexed by event ID → search hit with source reference**. See [implementation notes](docs/IMPLEMENTATION.md) for the interfaces.

Phase 6's dashboard implementation is ready for a manual browser trial. Its automated HTTP checks cover project selection data, handoff, source-linked records, pause, and project-scoped deletion. The remaining Phase 6 completion gate is an unfamiliar person opening the dashboard and finding an unfinished task without developer help. The saved MCP entry on this machine still points to the trial database; [the project workflow](docs/PROJECT_WORKFLOW.md#make-codex-read-the-real-database) gives the exact switch for normal use.

