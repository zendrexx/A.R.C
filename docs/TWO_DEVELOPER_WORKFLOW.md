# A.R.C. — two-developer workflow

This is the execution guide for the two developers. The phase goals and gates remain in [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md). Work on separate branches and agree on shared contracts before either branch changes them. A phase is complete only after its gate is tested.

## What works today

The current CLI can register a Git project, group explicitly recorded events into sessions, save notes and Git observations, run one configured test command, track evidence-backed task states, create candidate checkpoints, index summaries with local `all-minilm`, and search them. Codex can read that project evidence through the stdio MCP server. The user's fresh-session MCP trial succeeded. The physical disconnected-network trial remains open.

Collection and indexing are **manual today**. There is no file watcher, automatic test capture, offline chat, or VS Code dashboard yet. The local SQLite database is not synchronized between developers. Git commits and pushes are not required for A.R.C. to inspect a local project; a push is needed only to share source code between separate machines.

## Start using the finished prototype

On **each developer's machine**, open the local A.R.C. repository in a terminal. Complete the macOS installation in [README.md](../README.md) first, and keep local Ollama running with `all-minilm` installed. Each clone has its own ignored `.arc/` database and `.venv/` environment.

```bash
cd /path/to/A.R.C
source .venv/bin/activate
export ARC_DB="$PWD/.arc/arc.sqlite3"
arc init --test-command "$PWD/.venv/bin/python -m pytest -q"
arc session start "A.R.C. development"
arc state
```

During real work, record a decision or failure only when it matters. After meaningful **uncommitted** edits, capture Git state **before committing**, because the current capture command reads working-tree changes. Then record the configured test result. Run `arc index` after recording events so semantic search can find them. Finish with a candidate handoff and close the session:

```bash
arc capture
arc test
arc index
arc search "What changed in this project?" --semantic-only
arc state
arc checkpoint
arc session end
```

When there is a real decision, failure, or attempted fix, add it with `arc note --kind decision "..."`, `--kind error`, or `--kind attempt`; A.R.C. cannot reconstruct why a change was made from Git metadata alone. `arc capture` records local changed paths and a Git fingerprint. `arc test` really runs the configured command. `arc checkpoint` is an unconfirmed candidate. `arc session list` shows session IDs; `arc session show <actual-session-id>` shows one session's events. Use an actual ID from the command output, without angle brackets.

For a task you are actually implementing, run `arc task add "Task title"` and copy the returned `id`. Then link evidence with `arc capture --task ID` while the relevant edits are visible and `arc test --task ID`. `arc task claim ID "..."` records an unverified claim; `arc task confirm ID` succeeds only after linked changes and a current passing configured test, and should be used only after reviewing the work. `arc task history ID` shows the supporting records. Use the real ID in place of `ID`. A commit changes the Git fingerprint, so rerun `arc test --task ID` after committing if you want confirmation at the new fingerprint.

The current Codex MCP entry on the first machine points to `.arc/first-test.sqlite3`, which contains trial records. Normal `arc` commands above use `.arc/arc.sqlite3`. To make **new Codex sessions** read the real database, change the MCP entry once from this repository root:

```bash
codex_bin="$(find "$HOME/.vscode/extensions" -type f -path '*/bin/macos-aarch64/codex' -print -quit)"
"$codex_bin" mcp remove arc
"$codex_bin" mcp add arc \
  --env ARC_PROJECT="$PWD" \
  --env ARC_DB="$PWD/.arc/arc.sqlite3" \
  -- "$PWD/.venv/bin/python" -m arc.mcp_server
"$codex_bin" mcp list
```

If `codex` is already on your terminal path, use `codex` in place of `"$codex_bin"`. If the bundled binary path is absent, install the Codex CLI separately before these commands; the Python package does not install it. Restart the Codex session, then ask: “Use A.R.C. to show this project's current state and the latest session.” The MCP database path is saved in Codex configuration; changing the shell's `ARC_DB` later does not change that saved entry. Repeat this setup separately on Developer 2's machine, using that machine's absolute paths.

After editing A.R.C.'s own Python source, update this machine's noneditable install before using `arc` or restarting Codex's MCP process:

```bash
python -m pip install --no-deps --force-reinstall .
python -m pytest -q
```

## Parallel ownership and phase split

| When | Developer 1 — local AI and memory | Developer 2 — product and evidence | Integration gate |
|---|---|---|---|
| **Now: finish open Phase 2 validation; build Phases 3–5** | Own `arc/memory.py`, `scripts/evaluate_retrieval.py`, `tests/fixtures/retrieval_cases.json`, and memory tests. Expand the labelled incident set, measure false matches and latency, and run the physical offline search trial. Implement incident retrieval improvements for Phase 5 without claiming a similarity score proves a match. | Own `arc/store.py`, `arc/service.py`, `arc/git_evidence.py`, `arc/cli.py`, `arc/mcp_server.py`, and service/MCP tests. Complete Phase 3 correction and verification views; then add a compact, evidence-linked Phase 4 handoff from recorded decisions, failures, tasks, and sessions. | Both branches pass tests. A real session exposes the same event IDs through CLI and MCP; untested claims remain unverified. |
| **Then: Phases 6–7** | Tune retrieval from measured cases and help record offline, relevance, and false-match evidence. | Build the Phase 6 product views and second-agent path only after the handoff contract works. Lead the end-to-end demo flow. | Both developers run the Phase 7 gates on the demo machine and record measured results. |
| **Future: Phases 8–9** | Prepare indexing-queue design and then implement automatic embedding of eligible recorded events after the event contract is agreed. | Implement opt-in observation, deduplication, privacy controls, and supported test adapters. Own migrations. | Existing CLI/MCP evidence rules still pass; replayed events do not duplicate; new events index automatically. |
| **Future: Phases 10–11** | Implement evidence-grounded local chat and its stable request/response contract; evaluate `qwen3:1.7b` on the target Mac. | Provide deterministic time-range queries and build the VS Code extension shell against the agreed contract. Connect it after chat answers are validated. | Chat and extension show the same source IDs and verification state as CLI/MCP. |
| **Future: Phase 12** | Measure retrieval and chat quality/resource use. | Measure observation/UI reliability and prepare the demo. | Both repeat the disconnected end-to-end run on the Mac M1 8GB machine. |

The “Now” row is the next coding split. Developer 1 can work on retrieval and offline evaluation while Developer 2 works on task corrections and handoff. This overlaps implementation **within** the original phase order; it does not mark later phase gates complete early. The watcher, chatbot, and extension stay in their future phases.

## Shared interface and integration rules

| Boundary | Current agreement |
|---|---|
| Evidence | `ArcService` and `Store` own factual events. An agent claim or generated answer never changes verification state. |
| Identity | Every event keeps its ID and `arc:event/<id>` source reference. Existing session IDs, task IDs, and UTC timestamps keep their meanings. |
| Memory | `MemoryEngine` reads recorded events and writes vectors keyed by event ID; `SearchHit` in `arc/contracts.py` remains the shared result shape. Scores are ranking signals, not proof. |
| Consumers | CLI and MCP read the same project-scoped SQLite database. Preserve existing command and MCP tool names/result fields when adding capabilities. |
| Shared files | Agree before changing `arc/contracts.py`, database schema/migrations, event semantics, or public service/MCP response fields. Review the proposed field, migration, and a small example payload together. |

Do not have both developers edit the same shared file in parallel. Developer 1 should request a storage or API addition from Developer 2 with the desired input, output, and test case. Developer 2 should request ranking behavior from Developer 1 the same way. When a change crosses the boundary, agree on the contract first; then one owner makes the shared-file edit and both update their adapters.

## Branches, sharing, and daily merge

First commit and share this guide on `main` so both clones have the same instructions and baseline. On **Developer 1's clone**, create `dev1/memory`; on **Developer 2's separate clone**, create `dev2/product`. Both branches should start from that same main commit:

```bash
git add README.md docs/DEVELOPMENT_PLAN.md docs/IMPLEMENTATION.md docs/TWO_DEVELOPER_WORKFLOW.md
git commit -m "Document two-developer A.R.C. workflow"
git push origin main
```

Run those three commands once on the primary clone after reviewing this documentation. Then Developer 1 runs:

```bash
git switch main
git pull --ff-only
git switch -c dev1/memory
```

Developer 2 runs the same first two commands but uses `git switch -c dev2/product`. If the branches already exist, use `git switch` without `-c`. Work in separate clones or Git worktrees; two people should not share one working tree. On separate laptops, each developer pushes **their code branch** to GitHub and reviews/merges it through the normal Git workflow. Those pushes share source and docs; `.arc/` and `.venv/` are ignored and remain local. On one laptop, separate worktrees still need separate virtual environments and database paths.

Before either branch is merged, its owner runs `python -m pytest -q`; Developer 1 also runs `python -m scripts.evaluate_retrieval` when Ollama is available. After merging both branches, reinstall the package, run those checks again, and exercise `arc init → session start → task add → capture → test → index → search → checkpoint → session end → fresh MCP query` with real IDs. Record the actual result and any missing gate in the development plan. Run the disconnected-network trial on the demo machine; do not infer it from `OLLAMA_NO_CLOUD=1` alone.

### Copy-paste task for Developer 1's Codex

> Work on the Local AI/memory track in `docs/TWO_DEVELOPER_WORKFLOW.md`. Start from `dev1/memory`. Inspect the current `arc/memory.py`, retrieval fixtures, evaluation script, and Phase 2/5 gates in `docs/DEVELOPMENT_PLAN.md`. Expand meaningful labelled retrieval cases, quantify top-1/recall/false matches and latency on local Ollama, and improve ranking or rejection only if results support it. Keep `arc/contracts.py`, SQLite schema, `ArcService` public responses, CLI, and MCP unchanged. Add focused tests for behavior you change. Report measured outcomes and the physical offline test status; do not claim unrun checks passed.

### Copy-paste task for Developer 2's Codex

> Work on the Product/evidence track in `docs/TWO_DEVELOPER_WORKFLOW.md`. Start from `dev2/product`. Inspect Phase 3 and Phase 4 open gates in `docs/DEVELOPMENT_PLAN.md` and the current service/store/CLI/MCP code. Implement developer correction of task status with an auditable event and a usable verification view, then produce a compact evidence-linked handoff from recorded tasks, decisions, failures, and sessions. Preserve the existing task evidence rules and MCP tool behavior. Own any SQLite migration and ask Developer 1 before changing `arc/contracts.py` or memory-facing event fields. Add focused service/MCP tests and report the exact end-to-end commands and results.
