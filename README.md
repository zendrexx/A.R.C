# A.R.C. — Agent Recall & Continuity

A.R.C. is a local development-memory prototype. It records **selected** Git state, explicit notes, task claims, and configured test results in SQLite. A local Ollama embedding model makes those records searchable by meaning. A stdio MCP server lets a new Codex session request an evidence-backed project handoff.

This repository implements the core CLI/MCP prototype through Phase 5 of [the product plan](docs/DEVELOPMENT_PLAN.md). It has explicit session grouping, local search, auditable task correction/review, compact handoffs, and linked debugging incidents. File watching, the dashboard, and the offline chatbot are later phases.

One developer owns implementation; the teammate owns documentation, test records, and video promotion. Use the [project workflow](docs/PROJECT_WORKFLOW.md) for the current commands and implementation order, the [documentation/video checklist](docs/DOCUMENTATION_AND_VIDEO.md) for presentation work, and the [test evidence log](docs/TEST_RESULTS.md) for recorded results. A.R.C. reads local Git state; a Git push is needed only to share source or documentation between machines.

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

`arc index` sends the selected event summaries only to Ollama on `127.0.0.1`. Default search keeps cosine-ranked semantic results and says `"mode": "semantic"`. If Ollama is unavailable or records have not been indexed, ordinary search labels its FTS5 results `keyword_fallback`; `--semantic-only` instead requires the model and reports when indexing is needed. Indexing is still manual in this phase.

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

**No GitHub push is needed.** A.R.C. reads the local Git repository, including uncommitted edits and new untracked files; it does not require a commit, a remote, or internet access. In the current prototype, recording is explicit: run `arc capture` after relevant changes, `arc test` to record a configured test run, and `arc index` to make new events semantically searchable. Automatic file observation and automatic session start/stop are future work.

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

The tests cover unverified claims, auditable task correction, current versus stale tests and confirmations, handoff selection, incident links and cause separation, checkpoint freshness, privacy filtering, session grouping and migration, semantic ranking, keyword fallback, and real stdio MCP client/server calls. Live-model tests run when local Ollama and `all-minilm` are available; otherwise they skip. Run `python -m scripts.evaluate_retrieval` for the fixed seven-record semantic-versus-keyword comparison. The user-reported disconnected-network result still needs captured terminal output for the hackathon evidence package.

## Project roles and next gate

The implementation developer owns Python, SQLite, local retrieval, CLI, MCP, and future interface work. The teammate owns the setup walkthrough, test evidence log, presentation, and video. The shared technical flow is **recorded event → SQLite `events` row → embedding indexed by event ID → search hit with source reference**. See [implementation notes](docs/IMPLEMENTATION.md) for the interfaces.

Phase 5's linked incident history and conservative local search work in the CLI and MCP. A controlled live-model test retrieved a paraphrased prior error, separated a different cause, and rejected an unrelated query. Phase 6 interface work is next; [the project workflow](docs/PROJECT_WORKFLOW.md#implementation-order) lists the order. The saved MCP entry on this machine still points to the trial database; the workflow gives the exact switch for normal use.

