# A.R.C. — Agent Recall & Continuity

A.R.C. is a local development-memory prototype. It records **selected** Git state, explicit notes, task claims, and configured test results in SQLite. A local Ollama embedding model makes those records searchable by meaning. A stdio MCP server lets a new Codex session request an evidence-backed project handoff.

The CLI and MCP evidence store now also supports opt-in Git observation, automatic indexing, paginated history, and cited local answers. The VS Code extension integrates these features. The [product plan](docs/DEVELOPMENT_PLAN.md) describes the broader vision; [Phase 12 validation](docs/PHASE_12_VALIDATION.md) records the remaining release gates.

For a two-person implementation split and a practical daily-use sequence, see [the two-developer workflow](docs/TWO_DEVELOPER_WORKFLOW.md). Each developer uses a separate branch and local SQLite database. A.R.C. itself reads local Git state; only sharing source code between machines needs a Git push.

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

The setup commands register the real project database without adding sample incidents. For a separate example run, use the [first hands-on test](#first-hands-on-test). For actual development, start a session and follow [the current-use steps](docs/TWO_DEVELOPER_WORKFLOW.md#start-using-the-finished-prototype).

Use `arc search "database upgrade" --kind error` to filter by event type. Use `--keyword-only` to search without Ollama, or `--hybrid` to combine semantic and exact keyword rankings. Results include indexed and pending record counts; `score_kind` identifies how each ranking score was computed, and scores are not probabilities.

## Record real project progress

Use `arc --project /absolute/path/to/repository ...` to select a different Git project. Registration is explicit. The configured test command is an executable plus arguments; A.R.C. never executes a command found in a note or agent response.

```bash
arc task add "Implement login"
# Copy the returned task ID into the commands below.
arc task claim TASK_ID "Login is complete"
arc capture --task TASK_ID
arc test --task TASK_ID
arc state
arc task confirm TASK_ID
arc checkpoint
```

The claim alone remains **planned**. A linked Git observation can raise it to **implementation observed**. A passing configured test at the current Git fingerprint raises it to **tests passed**. Only an explicit `arc task confirm` marks it **completed/confirmed**. If the project changes afterward, the earlier test is no longer shown as current evidence. A checkpoint is saved as an **unconfirmed candidate** and reports when it becomes stale.

`arc capture` records changed paths and a Git fingerprint; it does not store source files or a Git diff. `arc test` stores the configured command, exit code, fingerprint, and a redacted tail of output. Avoid putting secrets in the configured command.

**No GitHub push is needed.** A.R.C. reads the local Git repository, including eligible uncommitted edits and untracked files. Manual commands remain available: `arc capture`, `arc test`, and `arc index`. Automatic observation requires an explicit opt-in and an active worker.

## Observe and ask locally

After registering the project, use the same database for CLI, extension, and MCP:

```bash
arc observer enable
arc watch
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

The search result should say `"mode": "semantic"` and include the recorded migration error with an `arc:event/<id>` reference. Repeat the search after disconnecting Wi-Fi to verify the local offline path. The fresh Codex MCP trial succeeded on 2026-10-09; the disconnected-network trial remains open.

## Connect to Codex

The MCP server is scoped to one registered project. Set `ARC_DB` to the database you want Codex to read (`first-test.sqlite3` for the trial or `arc.sqlite3` for normal use), then run this **once** from the repository root to add it to your local Codex configuration:

```bash
codex mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$ARC_DB" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
codex mcp list
```

If the terminal reports `codex: command not found`, use the bundled VS Code Codex binary and the real-database reconfiguration commands in [the two-developer guide](docs/TWO_DEVELOPER_WORKFLOW.md#start-using-the-finished-prototype). Changing `ARC_DB` in a terminal does not update an MCP entry that was already saved.

Restart the Codex session, then ask: **“Use A.R.C. to show this project's current state and what remains unfinished.”** The server offers `arc_get_project_state`, `arc_search_memory`, `arc_get_recent_changes`, `arc_get_task_history`, `arc_get_session_history`, `arc_get_event`, and `arc_create_checkpoint`. The last tool saves an unconfirmed candidate. Connecting the server makes returned project summaries available to the coding agent, so review what you record before enabling it.

The [official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp) documents local stdio servers and `codex mcp add`. The server uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). Ollama's [all-minilm model page](https://ollama.com/library/all-minilm) documents the model pull and local embedding endpoint; its [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) documents local-only mode.

## Tests

```bash
python -m pytest -q
```

The tests cover unverified claims, current versus stale test evidence, checkpoint freshness, privacy filtering, session grouping and migration, semantic ranking, hybrid and filtered retrieval, keyword fallback, and a real stdio MCP client/server round trip. The live-model test runs when local Ollama and `all-minilm` are available; otherwise it skips. Run `python -m scripts.evaluate_retrieval` for the fixed seven-record semantic-versus-keyword comparison. A physical disconnected-network trial remains to be recorded as hackathon evidence.

## Two developer boundary

| Developer | Owns | Files |
|---|---|---|
| **1 — Local AI/memory** | Ollama adapter, embedding index, semantic ranking, search evaluation | `arc/memory.py`, memory tests |
| **2 — Product/evidence** | Git observation, SQLite, verification rules, CLI, MCP | `arc/git_evidence.py`, `arc/store.py`, `arc/service.py`, `arc/cli.py`, `arc/mcp_server.py`, product tests |

Both developers agree before changing `arc/contracts.py` or the SQLite schema. The shared flow is **recorded event → SQLite `events` row → embedding indexed by event ID → search hit with source reference**. The product track owns the event truth; the memory track ranks only recorded evidence. See [implementation notes](docs/IMPLEMENTATION.md) for the interfaces and next checkpoints.

The [parallel phase schedule](docs/TWO_DEVELOPER_WORKFLOW.md#parallel-ownership-and-phase-split) gives each developer their next task, branch, integration gate, and a Codex prompt. The current MCP entry on this machine still points to the trial database; the guide includes the exact switch to the real database.

