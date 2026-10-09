# A.R.C. — Agent Recall & Continuity

**Pick up a project without rebuilding its history from old chats.** A.R.C. keeps a local, searchable record of your development sessions, decisions, Git changes, tasks, tests, and debugging attempts. It uses that record to show what happened, what remains unfinished, and which source events support each answer.

A.R.C. is an active prototype for macOS. It includes a command-line app, a local web dashboard, a VS Code extension, and an MCP server for coding agents such as Codex. The [development plan](docs/DEVELOPMENT_PLAN.md) describes the product goals; the [validation checklist](docs/PHASE_12_VALIDATION.md) shows which real-machine checks are still open.

## What A.R.C. helps you do

1. **Remember project context.** Save decisions, errors, attempted fixes, sessions, and selected Git activity. Search the record by meaning with a local embedding model, or use keyword search without a model.
2. **Hand off work to the next session.** `arc handoff` shows unfinished tasks, current evidence, the latest session, and selected decisions and failures with event references. A new coding agent can request the same handoff through MCP.
3. **Ask about recorded work.** `arc chat` answers with exact recorded summaries and citations. The local `qwen3:1.7b` model can select sources and write a short introduction; inspect the cited records before relying on its wording. An agent's claim is never proof of completion.
4. **Check progress before calling it done.** Link a task to observed Git changes and a configured test run. A.R.C. distinguishes planned, observed, tested, and explicitly confirmed work. Old tests become historical when the Git fingerprint changes.
5. **See the project in one place.** The browser dashboard shows the handoff, tasks and evidence, search, timeline, checkpoints, incidents, and local AI status. The VS Code extension adds Memory and Chat views in the editor.
6. **Collect routine changes automatically when you choose.** An opt-in observer records eligible Git path changes and commits, coalesces repeated saves, and indexes pending summaries locally. It does not run tests or infer why a change was made; record those explicitly.

Everything A.R.C. records lives in a local SQLite database. Git observation stores paths, commit metadata, and a fingerprint, not file bodies or diffs. A.R.C. can work after installation without an internet connection when its local Ollama models are already downloaded. The [recorded offline trial](docs/PHASE_12_VALIDATION.md#physical-offline-trial--2026-10-10) covers CLI search, cited chat, and a fresh MCP handoff.

## Phase 10–12 progress

| Phase | Current status |
|---|---|
| **10 · Offline project-history chat** | **Focused gate complete.** A [physical Wi-Fi-off trial](docs/phase10-offline-report.json) on the M1 Mac answered the planned questions from local evidence, resolved every returned citation, and handled missing rationale and long timelines. |
| **11 · VS Code Memory and Chat** | **Implemented.** The latest [validation run](docs/phase11-12-validation-report.json) passed 15 compiled extension tests. A live Extension Development Host review remains open. |
| **12 · Reliability and release validation** | **In progress.** The same run passed 54 Python tests and a disposable observer, test, chat, and MCP workflow. The [Phase 12 checklist](docs/PHASE_12_VALIDATION.md) still calls for a full offline editor workflow, sustained resource measurements, broader answer accuracy checks, and a backup recording. |

The current chat can write a model-generated introduction. One [live Phase 12 answer](docs/PHASE_12_VALIDATION.md#phase-1112-validation-rerun--2026-10-10) cited the right decision but added reasons absent from that record, so a valid citation alone does not establish that all of the model's wording is supported.

## Set up on macOS

Use macOS 14+, Python 3.11+, and Git. The CLI and dashboard use Python; semantic search needs a running local [Ollama](https://ollama.com/) server with `all-minilm`. Model-assisted chat and the VS Code Chat view also need `qwen3:1.7b`. VS Code 1.90+ and Node.js/npm are needed only for the extension. The project is being validated on an M1 Mac with 8 GB of memory; that is a test target, not a proven minimum. The first package install and model downloads need internet.

From the A.R.C. repository root:

```bash
brew install python@3.11 ollama
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install '.[dev]'
arc --help
```

Start Ollama in a separate terminal and leave it running. If Ollama is already serving on `127.0.0.1:11434`, use that instance instead.

```bash
OLLAMA_NO_CLOUD=1 ollama serve
```

Back in the activated environment at the repository root, download the local models and register this Git repository:

```bash
ollama pull all-minilm
ollama pull qwen3:1.7b
ollama list
curl -fsS http://127.0.0.1:11434/api/tags
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc init --test-command "$PWD/.venv/bin/python -m pytest -q"
arc ai-status
arc state
```

`ARC_DB` chooses the SQLite file shared by the CLI, dashboard, extension, and MCP server. Export it again in each new terminal, or set the extension's **A.R.C.: Database Path** to the same absolute path. Without `ARC_DB`, the CLI uses its application-data default. To register another Git repository in this database, use `arc --project /absolute/path/to/repository init` and optionally add its own `--test-command`. Run later CLI commands with the same `--project` option. The test command is an approved executable and arguments, not shell syntax.

The regular package install is intentional: an editable install on the validation Mac can leave `arc` unable to import its package. After editing A.R.C.'s Python source, run `python -m pip install --no-deps --force-reinstall .` before using the installed command again.

### First use: record, find, and hand off work

Run these from the registered project with the same `ARC_DB`:

```bash
arc session start "Project work"
arc note --kind decision "Describe a real decision and why you made it"
arc capture                         # record eligible current Git changes
arc test                            # run the test command configured at init
arc index                           # make new records semantically searchable
arc search "Why did we make that decision?"
arc handoff
arc chat "Where did we leave off?"
arc session end
```

Use your actual decision in the note. `arc capture` records paths and a Git fingerprint, including eligible uncommitted work; it does not save source code. `arc test` records the configured command, exit code, fingerprint, and a redacted output tail. `arc handoff` works directly from SQLite without indexing or Ollama. If Ollama is unavailable, `arc search "query" --keyword-only` and `arc chat "question" --keyword-only` still show recorded keyword evidence. Model-assisted chat requires the local chat model even when the question is about the timeline.

## Open the web dashboard

With the virtual environment active and `ARC_DB` set as above:

```bash
arc dashboard
```

Open `http://127.0.0.1:8765/` if the browser does not open automatically. Keep the command running while using the dashboard; press `Ctrl+C` to stop it. Use `arc dashboard --no-browser --port 8766` if you need another port.

The dashboard lets you select or register a local Git project, review the handoff, inspect source events and task evidence, search memory, browse a timeline, save candidate checkpoints, and revisit incidents. **Settings & privacy** can check the local embedding model, index pending events, pause new manual records, or clear one project's A.R.C. memory after an exact confirmation. Clearing memory leaves the source files and project registration in place. The dashboard serves only on this computer's loopback address. It reads recorded activity; keep using the CLI or extension for Git observation and configured tests.

## Turn on automatic observation

After registering a project, run:

```bash
arc observer start
arc observer status
```

`start` enables observation and launches a detached worker. It polls eligible Git state about every five seconds, records new reachable commits after a worker restart, and retries small batches of pending local indexing. The worker creates an observation session when needed. It skips generated and sensitive paths such as `.env`, keys, and `.arc/`; a Git push is not required. Edits made and reverted between polls may be missed. Tests run outside `arc test` or the extension are not recorded as verified tests.

Use `arc observer pause` to stop collecting temporarily, `arc observer resume` to start from the current state, and `arc observer stop` to disable observation and terminate the worker. Activity during a pause is not imported on resume. For a foreground worker, run `arc observer enable` followed by `arc watch`. In VS Code, **Enable Automatic Observation** starts and supervises the worker for the connected project, so you do not need a separate terminal worker there.

## Record real project progress

Create a task and save its returned ID, then attach evidence after making a relevant code change:

```bash
task_id="$(arc task add "Describe the real task" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
arc task claim "$task_id" "Describe the intended work"    # an unverified claim
# Make the code change here.
arc capture --task "$task_id"
arc test --task "$task_id"
arc task review "$task_id"
arc task confirm "$task_id"                               # after review and a current passing test
```

`arc task review` shows supporting events and missing checks. A claim stays unverified; a confirmation requires linked observed changes and a passing configured test at the current Git fingerprint. If the code changes or you commit afterward, rerun the test before relying on the old result as current. Use `arc task correct TASK_ID --to planned --reason "..."` to record a downward correction. The [project workflow](docs/PROJECT_WORKFLOW.md) has the full task and session rhythm.

## Remember a debugging incident

Save an error, link attempts, and record a reported resolution so a later session can find the experience:

```bash
error_id="$(arc note --kind error "Describe the actual error" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
incident_id="$(arc incident open "$error_id" --cause "Known cause, if established" | python -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
arc incident attempt "$incident_id" "Describe what you tried" --outcome helped
arc incident resolve "$incident_id" "Describe the fix you applied"
arc incident show "$incident_id"
arc index
arc incident search "Describe a similar error"
```

Omit `--cause` if the cause is unknown. A reported resolution is a record of what someone said worked, not automatic proof of a fix. Search returns candidates and keeps explicitly different causes separate. You can attach a passing current test to a resolution with `--test-event TEST_ID`; see `arc incident resolve --help` and the [implementation notes](docs/IMPLEMENTATION.md).

## Ask about project history

After the models are installed, ask questions in the CLI or VS Code Chat view:

```bash
arc chat "What happened yesterday?"
arc chat "What errors did we fix?"
arc chat "Why did we use a local browser dashboard?"
arc chat "Summarize our development timeline"
arc chat "What happened from 2026-10-01 to 2026-10-09?" --timezone-offset 480
```

Calendar words use the machine's current UTC offset by default; `--timezone-offset 480` explicitly means UTC+08:00. A named task or its ID retrieves its linked history and current evidence state. A “why” answer needs a recorded decision, cause, explanatory note, or commit message; a changed file alone cannot establish the reason. “What errors did we fix?” shows linked *reported* resolutions and identifies whether a configured test is linked and still current. It does not claim that a test proves the error is fixed.

Timeline answers count activity by local day, group repeated Git watcher observations into one cited example per day, and show earlier milestones. The raw `arc timeline` command retains every event. When chat returns `next_offset` and `snapshot_rowid`, pass both back as `arc chat "same question" --offset N --snapshot S` to load the next stable page; VS Code has a **Load older history** button. `arc chat "question" --keyword-only` works without Ollama and keeps the same evidence labels. The [Phase 10 offline report](docs/phase10-offline-report.json) records the seven-question real-model trial.

## Use A.R.C. in VS Code

The extension is currently run from source. Install VS Code 1.90+ and Node.js/npm, then:

```bash
cd extension
npm ci
npm test
```

Open this `extension/` folder in VS Code and press **F5**. In the Extension Development Host, open your target Git project. Select the A.R.C. activity bar icon, then **Connect Project** or **Create Project**. Set **A.R.C.: Python Path** if the extension cannot find the environment containing `arc-memory`; set **A.R.C.: Database Path** to the same absolute SQLite path used by the CLI. The Memory view shows tasks, changes, events, checkpoints, and observer status. The Chat view answers from cited records and offers **Inspect** on each source. [Extension setup and controls](extension/README.md) has the full walkthrough.

## Give a new Codex session the handoff

If you use the Codex CLI, add A.R.C.'s local stdio MCP server once from the A.R.C. repository root with the virtual environment active and `ARC_DB` set to the database you want to share:

```bash
codex mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$ARC_DB" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
codex mcp list
```

Restart Codex and ask: **“Call `arc_get_project_handoff`. What is unfinished, what is currently verified, and which source events support that handoff?”** The server also exposes project state, search, task review, incidents, timeline, and individual event records. The saved MCP entry keeps the database path used when you added it; changing a shell's `ARC_DB` later does not change that entry. For another project, set `ARC_PROJECT` to that repository's absolute path and use the same registered database. If `codex` is not on your path, the [project workflow](docs/PROJECT_WORKFLOW.md#make-codex-read-the-real-database) gives the VS Code bundled-binary route. The Codex CLI is a separate install.

## Other features and useful commands

| Need | Command or view |
|---|---|
| Check the evidence-backed project state | `arc state` or dashboard **Overview** |
| Find a note, decision, or error | `arc search "query"`; add `--kind error`, `--keyword-only`, `--semantic-only`, or `--hybrid` |
| Browse older activity | `arc timeline --kind test`, `arc session list`, or dashboard **Timeline** |
| Inspect an answer's citation | `arc event EVENT_ID` or an **Inspect** button in VS Code |
| Save a handoff snapshot | `arc checkpoint`; it is an unconfirmed candidate that can become stale |
| Check local model readiness | `arc ai-status` |
| Use a different registered project | `arc --project /absolute/path/to/repository ...` |

For the command reference and implementation details, see the [project workflow](docs/PROJECT_WORKFLOW.md) and [implementation notes](docs/IMPLEMENTATION.md). For recorded validation results and remaining release checks, see the [Phase 12 checklist](docs/PHASE_12_VALIDATION.md) and [test log](docs/TEST_RESULTS.md).

## Run the tests

```bash
source .venv/bin/activate
python -m pytest -q
```

The suite covers task verification, handoffs, incidents, local retrieval and fallbacks, dashboard routes, observer behavior, and MCP calls. Live-model tests use local Ollama when available and skip otherwise. Run `npm test` in `extension/` for its compile and integration checks.
