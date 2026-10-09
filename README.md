# A.R.C. — Agent Recall & Continuity

A.R.C. is a local development-memory prototype. It records **selected** Git state, explicit notes, task claims, and configured test results in SQLite. A local Ollama embedding model makes those records searchable by meaning. A stdio MCP server lets a new Codex session request an evidence-backed project handoff.

This repository currently implements the **Phase 0 runnable slice** and explicit session grouping from Phase 1 of [the product plan](docs/DEVELOPMENT_PLAN.md). It is a CLI and MCP prototype; file watching, the dashboard, and the offline chatbot are later phases.

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
arc note --kind error "SQLite schema migration failed because the users table was missing"
arc note --kind decision "Use a green accent for the dashboard"
arc index
arc search "Why did the database upgrade crash?" --semantic-only
arc state
```

`arc index` sends the selected note summaries only to Ollama on `127.0.0.1`. The search response must say `"mode": "semantic"`. If Ollama is unavailable, ordinary `arc search` labels its results `keyword_fallback`; `--semantic-only` returns an error instead. Run `arc index` again after recording new events.

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

The search result should say `"mode": "semantic"` and include the recorded migration error with an `arc:event/<id>` reference. Repeat the search after disconnecting Wi-Fi to verify the local offline path. Once this passes, connect MCP using the section below and try a fresh Codex session against this test database. Those two user-run trials remain open in the development plan.

## Connect to Codex

The MCP server is scoped to one registered project. Set `ARC_DB` to the database you want Codex to read (`first-test.sqlite3` for the trial or `arc.sqlite3` for normal use), then run this **once** from the repository root to add it to your local Codex configuration:

```bash
codex mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$ARC_DB" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
codex mcp list
```

Restart the Codex session, then ask: **“Use A.R.C. to show this project's current state and what remains unfinished.”** The server offers `arc_get_project_state`, `arc_search_memory`, `arc_get_recent_changes`, `arc_get_task_history`, `arc_get_session_history`, `arc_get_event`, and `arc_create_checkpoint`. The last tool saves an unconfirmed candidate. Connecting the server makes returned project summaries available to the coding agent, so review what you record before enabling it.

The [official Codex MCP guide](https://learn.chatgpt.com/docs/extend/mcp) documents local stdio servers and `codex mcp add`. The server uses the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk). Ollama's [all-minilm model page](https://ollama.com/library/all-minilm) documents the model pull and local embedding endpoint; its [FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx) documents local-only mode.

## Tests

```bash
python -m pytest -q
```

The tests cover unverified claims, current versus stale test evidence, checkpoint freshness, privacy filtering, session grouping and migration, semantic ranking, keyword fallback, and a real stdio MCP client/server round trip. The live-model test runs when local Ollama and `all-minilm` are available; otherwise it skips. A physical disconnected-network trial and actual fresh Codex-session handoff remain to be recorded as hackathon evidence.

## Two developer boundary

| Developer | Owns | Files |
|---|---|---|
| **1 — Local AI/memory** | Ollama adapter, embedding index, semantic ranking, search evaluation | `arc/memory.py`, memory tests |
| **2 — Product/evidence** | Git observation, SQLite, verification rules, CLI, MCP | `arc/git_evidence.py`, `arc/store.py`, `arc/service.py`, `arc/cli.py`, `arc/mcp_server.py`, product tests |

Both developers agree before changing `arc/contracts.py` or the SQLite schema. The shared flow is **recorded event → SQLite `events` row → embedding indexed by event ID → search hit with source reference**. The product track owns the event truth; the memory track ranks only recorded evidence. See [implementation notes](docs/IMPLEMENTATION.md) for the interfaces and next checkpoints.

