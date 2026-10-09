# A.R.C. project workflow

A.R.C. has one implementation developer. The second team member owns documentation, test records, the product story, and video promotion. The phase goals and evidence rules stay in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). [DOCUMENTATION_AND_VIDEO.md](DOCUMENTATION_AND_VIDEO.md) gives the second team member concrete deliverables.

## Current position

The CLI, local SQLite evidence store, explicit sessions, Git capture, configured test recording, local `all-minilm` search, and stdio MCP integration work. A disconnected-network semantic search succeeded according to the user's 2026-10-09 trial. Phase 3 task correction/review, Phase 4 handoff, and Phase 5 linked incident search work through CLI and MCP. Controlled local-model tests passed for paraphrased error retrieval, cause separation, and unrelated-query rejection. Automatic watching, indexing, chat, and the VS Code dashboard are later phases.

Search and event collection still require explicit commands. The real `.arc/arc.sqlite3` database holds task `ccd44503aac9`, which the developer confirmed at its earlier Git fingerprint. Subsequent Phase 5 file changes make that test and confirmation historical under the current-state rules; the confirmation event remains available in task history. `.arc/first-test.sqlite3` contains trial records. Databases and virtual environments are ignored by Git.

## Use the current prototype

Complete the macOS setup in [README.md](../README.md), keep local Ollama running, then work from this repository root:

```bash
source .venv/bin/activate
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc init --test-command "$PWD/.venv/bin/python -m pytest -q"
arc session start "A.R.C. development"
arc state
```

After a meaningful uncommitted change, capture it **before committing**; the current capture command reads working-tree changes. Then record the configured test and index new summaries:

```bash
arc capture
arc test
arc index
arc search "What changed in this project?" --semantic-only
arc state
arc handoff
arc checkpoint
arc session end
```

For a real decision, error, or attempted fix, use `arc note --kind decision "..."`, `--kind error`, or `--kind attempt`. A.R.C. cannot recover a reason from changed paths alone. `arc handoff` selects recorded context immediately; `arc index` is only needed for semantic search. `arc session list` returns session IDs; `arc session show ID` displays that session. `arc event ID` resolves a search hit's `arc:event/ID` reference.

For debugging experience, follow [the incident walkthrough](../README.md#remember-a-debugging-incident). `arc incident open` links an error event, `attempt` records an outcome, and `resolve` records a reported resolution with optional current passing test evidence. `arc incident search` uses local embeddings after `arc index`, falls back conservatively to keywords, and keeps a different recorded cause separate. `arc incident show` exposes every source reference for review.

To track a task, follow the [README task example](../README.md#record-real-project-progress): enter a real title and let the shell save the returned ID as `task_id`. Use `arc capture --task "$task_id"`, `arc test --task "$task_id"`, and `arc task review "$task_id"` after relevant edits. A claim remains unverified. `arc task confirm "$task_id"` requires observed changes and a current passing configured test, and should follow review. If earlier evidence is wrong or insufficient, use `arc task correct "$task_id" --to planned --reason "Previous status was inaccurate"` or `--to implementation_observed --reason "The test needs repeating"`; the latter requires a linked Git change. Corrections are saved as events and cannot set a tested or confirmed state. A commit changes the Git fingerprint, so rerun `arc test --task "$task_id"` after committing if you need confirmation at the new fingerprint.

After editing A.R.C.'s Python source, update the installed command before using `arc` or restarting the MCP process on this Mac:

```bash
python -m pip install --no-deps --force-reinstall .
python -m pytest -q
```

## Make Codex read the real database

The current Codex MCP entry on this Mac points to `.arc/first-test.sqlite3`. To switch new Codex sessions to `.arc/arc.sqlite3`, run from the repository root:

```bash
codex_bin="$(find "$HOME/.vscode/extensions" -type f -path '*/bin/macos-aarch64/codex' -print -quit)"
"$codex_bin" mcp remove arc
"$codex_bin" mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$PWD/.arc/arc.sqlite3" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
"$codex_bin" mcp list
```

If `codex` is already on the terminal path, use `codex` in place of `"$codex_bin"`. If the bundled path is absent, install the Codex CLI separately; the Python package does not install it. Restart Codex and ask: “Call `arc_get_project_handoff` and explain the unfinished task, currently verified work, and relevant source events.” The MCP database path is saved in Codex configuration; changing `ARC_DB` in a shell later does not update it.

## Implementation order

1. **Done — Phase 3 CLI/MCP gate:** auditable downward task correction and verification review, while only linked, current test evidence supports a tested state.
2. **Done — Phase 4:** a fresh Codex session retrieved source-linked real-project context. The developer explicitly confirmed task `ccd44503aac9` afterward; that confirmation is retained as historical evidence when Git changes.
3. **Done — Phase 5 controlled gate:** incident errors, causes, attempts, reported resolutions, and tests are linked in SQLite; CLI/MCP retrieval separated similar wording with different causes and rejected an unrelated local-model query.
4. **Now — Phases 6–7:** build the usable interface and run wider real-project, privacy, retrieval, offline, and unfamiliar-user trials. The teammate records the evidence and produces the demo assets from actual results.
5. **Future — Phases 8–12:** add automatic observation, indexing, local chat, and the VS Code extension only after the MVP gates. Re-estimate durations for one implementation developer.

The evidence boundary remains **recorded event → SQLite event ID → embedding keyed by event ID → source-linked search hit**. Keep `arc/contracts.py`, SQLite migrations, and public CLI/MCP response fields compatible when extending it. The documentation/video lead can review setup and demo clarity without editing implementation files.

## Validation and handoff rhythm

After a meaningful implementation change, run `python -m pytest -q`; for search changes also run `python -m scripts.evaluate_retrieval` with local Ollama available. Exercise the actual CLI/MCP path using real IDs, record what passed or failed, and update the plan's checkboxes only for observed results. A.R.C. does not need GitHub pushes to inspect local work. Pushes are for sharing source code and documentation with the teammate.
