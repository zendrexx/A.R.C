# A.R.C. VS Code extension

Phase 11 integration: a native Memory tree and a local Chat view backed by the Python CLI and shared SQLite database. Automatic observation is opt-in. Chat shows cited recorded evidence and requires local `qwen3:1.7b` for source selection and optional short introductions; the view reports when Ollama or the model is missing.

## Run

1. Install the Python package with `python -m pip install '.[dev]'` from the repository root using Python 3.11+. Reinstall after backend source changes.
2. Register your target Git repository with `arc init`, using the same database as CLI/MCP.
3. Run `npm ci` and `npm test` in `extension/`.
4. Open `extension/` in VS Code and press F5.
5. In the Extension Development Host, open your target project, select A.R.C. and **Connect Project**.

Set **A.R.C.: Python Path** if Python is not in your project's `.venv`. Set **A.R.C.: Database Path** to the absolute SQLite path used by CLI/MCP. Empty uses the backend's ARC_DB/platform default; databases are never guessed.

Memory includes project/session status, observer state, index counts, tasks and verification, Git changes, recent events, checkpoint freshness, evidence JSON previews and file navigation. Commands provide search, capture, indexing, configured tests, checkpoints, refresh, timeline filters, observation controls, and disconnect. Multi-root selection scopes requests to one project. First connection asks for consent; **Enable Automatic Observation** asks separately before collecting. Pause and resume require that opt-in.

An enabled observer polls every five seconds and indexes two pending summaries per retry. Pause stops collection; resume discards the paused interval. Disable stops the worker. Disconnect or closing the workspace cancels requests and terminates the observer process tree. Reopening a previously approved single-folder workspace reconnects and restores persisted records. An explicit disconnect clears that automatic reconnect selection.

Ask questions in Chat and use **Inspect** buttons to open each cited event. Today/yesterday use the editor's current local UTC offset. Older timeline pages have a continuation button. Chat renders evidence as text with a restrictive content-security policy; it cannot execute commands or change task verification. The local model may write a short introduction; inspect the cited records because a valid citation does not guarantee every phrase is supported. If the local model requirement is unmet, the view reports it and asking is blocked; the CLI keeps a `--keyword-only` escape. External task/test adapters, daylight-saving-aware historical timezone rules, and a dedicated Ollama health view are not implemented.

`npm test` compiles the extension and checks its backend and activation lifecycle with mocks. Run `python -m scripts.validate_phase12` from the repository root after installing the current Python package to exercise a disposable project, real observer, CLI, and fresh MCP session. The [Phase 11/12 rerun](../docs/phase11-12-validation-report.json) passed 15 extension tests and a disposable integration workflow. Extension-host visual checks, a full offline editor workflow, sustained resource measurements, and broader answer accuracy remain open; see [the validation checklist](../docs/PHASE_12_VALIDATION.md).

References: official [Tree View API](https://code.visualstudio.com/api/extension-guides/tree-view) and [Webview API](https://code.visualstudio.com/api/extension-guides/webview).
