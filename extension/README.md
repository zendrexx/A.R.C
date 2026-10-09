# A.R.C. VS Code extension

Phase 11 integration: a native Memory tree and a local Chat view backed by the Python CLI and shared SQLite database. Automatic observation is opt-in. Local Ollama enhances search and conversational answers; recording, evidence search, sessions, and handoffs remain available without it.

## Automatic local AI

After initial project connection and observation consent, approved workspaces reconnect when VS Code starts. A.R.C. checks the loopback Ollama API and reuses a running server. If installed Ollama is stopped, it starts a hidden server without opening a Terminal. Set `arc.ollama.autoStart` to false to disable that startup; existing servers can still be used.

The embedding model defaults to `all-minilm`. Choose your installed conversational model with **ARC: Select AI Model**; no chat model is assumed. Model preferences are saved in `arc.models.embedding` and `arc.models.chat` and apply to CLI requests and automatic indexing. Missing selected models ask for download permission once. **ARC: Download Model** offers another explicitly confirmed download. Ollama itself must be installed once.

Health checks list installed models without loading them. Pending summaries are indexed in batches of two, at most every 30 seconds. Records stay queued while AI is unavailable. Connection failures retry with a bounded backoff. Managed servers bind to loopback with `OLLAMA_NO_CLOUD=1`, one loaded model, and one parallel request. A.R.C. requests validated local model names and does not alter cloud settings on an independently running server. No shared Ollama server is terminated on disconnect or reload.

## Sidebar and Quick Actions

The native **A.R.C. Quick Actions** view has **Open Dashboard**, **Ask A.R.C.**, and **Quick Actions**. Expand **AI Models** to see server status and selected models, choose a model with Quick Pick, or open the AI controls dropdown for load/unload, downloads, status, retries, and settings. The status bar opens Quick Actions too.

Quick Actions groups Dashboard, AI Models, Memory and Search, Sessions and Handoffs, and Settings. Every choice invokes the corresponding existing command. Use the Command Palette (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux) and search for **ARC:**.

**Open Dashboard** starts or reuses the existing Python dashboard and opens the default browser with the connected project selected. `arc.dashboard.url` supplies its actual local address and port (default `http://127.0.0.1:8765`). A health check verifies the database identity; a port serving another application/database produces an error instead of opening the wrong project. Shared services are not terminated on editor disconnect.

Manual model activation uses the same SQLite model lease as indexing/chat. It unloads the other selected model first if that model is loaded; it does not assume hardware can keep both loaded. Model operations use a short idle lifetime. These manual controls supplement automatic startup, recording, indexing, sessions, and handoffs.

Session records are persisted in SQLite as activity occurs. The next connection loads a **Session handoff** in Memory, even while AI is offline. First-time project registration and observation opt-in are still required.

## Run

1. Install the Python package with `python -m pip install '.[dev]'` from the repository root using Python 3.11+. Reinstall after backend source changes.
2. Register your target Git repository with `arc init`, using the same database as CLI/MCP.
3. Run `npm ci` and `npm test` in `extension/`.
4. Open `extension/` in VS Code and press F5.
5. In the Extension Development Host, open your target project, select A.R.C. and **Connect Project**.

Set **A.R.C.: Python Path** if Python is not in your project's `.venv`. Set **A.R.C.: Database Path** to the absolute SQLite path used by CLI/MCP. Empty uses the backend's ARC_DB/platform default; databases are never guessed.

Memory includes project/session status, observer state, index counts, tasks and verification, Git changes, recent events, checkpoint freshness, evidence JSON previews and file navigation. Commands provide search, capture, indexing, configured tests, checkpoints, refresh, timeline filters, observation controls, and disconnect. Multi-root selection scopes requests to one project. First connection asks for consent; **Enable Automatic Observation** asks separately before collecting. Pause and resume require that opt-in.

An enabled observer polls every five seconds and indexes two pending summaries per retry. Pause stops collection; resume discards the paused interval. Disable stops the worker. Disconnect or closing the workspace cancels requests and terminates the observer process tree. Reopening a previously approved single-folder workspace reconnects and restores persisted records. An explicit disconnect clears that automatic reconnect selection.

Ask questions in Chat and use **Inspect** buttons to open each cited event. Today/yesterday use the editor's current local UTC offset. Older timeline pages have a continuation button. Chat renders evidence as text with a restrictive content-security policy. Action requests use an allowlist of A.R.C. commands; enabling observation opens its permission popup. The local model may write a short introduction; inspect the cited records because a valid citation does not guarantee every phrase is supported. Without the chat model, questions use recorded evidence and keyword search. External task/test adapters and daylight-saving-aware historical timezone rules are not implemented.

`npm test` compiles the extension and checks its backend and activation lifecycle with mocks. Run `python -m scripts.validate_phase12` from the repository root after installing the current Python package to exercise a disposable project, real observer, CLI, and fresh MCP session. The [Phase 11/12 rerun](../docs/phase11-12-validation-report.json) passed 15 extension tests and a disposable integration workflow. Extension-host visual checks, a full offline editor workflow, sustained resource measurements, and broader answer accuracy remain open; see [the validation checklist](../docs/PHASE_12_VALIDATION.md).

References: official [Tree View API](https://code.visualstudio.com/api/extension-guides/tree-view) and [Webview API](https://code.visualstudio.com/api/extension-guides/webview).
