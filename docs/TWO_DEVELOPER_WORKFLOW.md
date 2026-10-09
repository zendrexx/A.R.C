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

The phase numbers are **product milestones**, not a phase assigned to one person. Developer 1 has substantial work before Phase 10: retrieval, evidence selection for handoffs, incident matching, evaluation, and automatic indexing. Developer 2 owns collection, verification, service integration, and the interface. Both work during each milestone, often on different modules.

| Phase and status | Developer 1 — local AI and memory | Developer 2 — product and evidence | Shared gate |
|---|---|---|---|
| **0–1: prototype built; offline gate open** | Embedding experiment and semantic lookup are built; run the remaining disconnected-network proof. | Registration, SQLite, Git capture, sessions, tests, and MCP are built; keep evidence semantics stable. | A fresh agent reads a real session; offline lookup still needs a physical trial. |
| **2: search built; broader validation open** | Own `arc/memory.py`, retrieval fixtures, and `scripts/evaluate_retrieval.py`. Add realistic paraphrases and unrelated queries; measure top-1, recall, false matches, and latency. | Supply correctly labelled source events and keep `Store` queries compatible with search. | Search returns resolvable event IDs and measured relevance results. |
| **3: next product gate** | In parallel, begin the **Phase 4** handoff selector using recorded event summaries and task states; this is Developer 1's separate coding task while Phase 3 is finished. | Add auditable task-status correction and a verification view in service/CLI/MCP. Own any schema migration. | Claims remain unverified without observed changes and a current passing configured test. |
| **4: handoff** | Own the ranking/selection logic for unfinished tasks, decisions, failures, and attempts. Implement it in a new memory-side module such as `arc/handoff.py`; return event IDs and reasons for selection. | Feed the selector recorded evidence, expose the compact handoff through `ArcService` and MCP, and retain checkpoint freshness rules. | A fresh Codex session gets a short handoff with inspectable source references. |
| **5: incident memory** | Own incident matching and rejection in a new memory-side module such as `arc/incident.py`; evaluate related versus unrelated failures and similar symptoms with different causes. | Persist links among error, attempt, outcome, and test evidence; expose their history without inventing a verified fix. | A past incident is retrieved with its actual attempt/outcome evidence. |
| **6: product interface** | Define the search result and explanation payload the views need; tune ranking and empty-result behavior against real queries. | Build the dashboard, timeline, task/verification views, and agent integration. | The views and MCP resolve the same `arc:event/<id>` records. |
| **7: MVP validation** | Lead retrieval, false-match, offline-model, and latency measurement on the demo machine; document actual numbers. | Lead full workflow, usability, privacy, and fresh-agent checks; record the backup demo. | Both verify the complete local workflow and compare it with the baseline. |
| **8: future automatic observation** | Define which observed event summaries are eligible for embedding, measure expected indexing load, and prepare queue tests against the agreed event contract. | Own the opt-in file/Git watcher, deduplication, sensitive-path filters, pause controls, and session capture. | Replayed observations do not duplicate and excluded data is not indexed. |
| **9: future automatic indexing** | Own the bounded, persistent `all-minilm` indexing queue, retries, freshness status, and time-filtered ranking. | Own supported test-result adapters, evidence linkage, and database migration. | New eligible events become searchable without `arc index`; evidence rules survive. |
| **10: future local chat** | Own `qwen3:1.7b` chat, bounded RAG retrieval, citation validation, missing-evidence responses, and long-history summaries. | Own deterministic date/task/error queries and service access for chat. | Offline answers cite recorded evidence and never upgrade task state. |
| **11: future VS Code extension** | Stabilize chat/search response contracts and measure model cold start, memory use, and citation behavior under the editor. | Build and connect the Chat and Memory views, workspace detection, and controls. | Extension, CLI, and MCP show consistent event IDs and statuses. |
| **12: future final validation** | Measure answer quality, retrieval misses, citation correctness, and local model resource use. | Measure observer and extension reliability, CPU/RAM, and end-to-end usability. | Both repeat the disconnected workflow on the target Mac. |

Phases 8–12 remain future work. Preparing a module or fixture early does not complete a later phase gate. The immediate balanced split is **Developer 1: Phase 2 evaluation plus the Phase 4 evidence selector** and **Developer 2: Phase 3 corrections plus the Phase 4 service/MCP wiring**. Next, they jointly complete Phase 5: Developer 1 handles matching, while Developer 2 handles incident evidence links.

Before implementing the Phase 4 selector, agree on a small input/output contract: each candidate supplies `event_id`, `kind`, `summary`, `created_at`, `source_ref`, and optional `task_id`; the selector returns chosen event IDs with a selection reason. Developer 2 owns loading and verifying those facts. Developer 1 owns deciding which are relevant. This keeps the work parallel without two branches changing `arc/store.py` or `arc/service.py` at once.

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

> Work on Developer 1's Local AI/memory track in `docs/TWO_DEVELOPER_WORKFLOW.md`. Start from `dev1/memory`. First, expand labelled retrieval cases and measure top-1, recall, false matches, and latency with local Ollama; run the physical offline trial if possible. Then implement the Phase 4 evidence selector as a separate memory-side module that accepts recorded event summaries and task states and returns chosen event IDs with reasons. Agree on its input/output fields with Developer 2 before coding. Own ranking and relevance; leave storage, task status, CLI, and MCP wiring to Developer 2. Add focused tests and report measured outcomes without claiming unrun checks passed. Later phases also assign you incident matching (5), retrieval evaluation (6–7), automatic indexing (9), grounded chat (10), and model validation (11–12).

### Copy-paste task for Developer 2's Codex

> Work on Developer 2's Product/evidence track in `docs/TWO_DEVELOPER_WORKFLOW.md`. Start from `dev2/product`. Inspect Phase 3 and Phase 4 open gates and the current service/store/CLI/MCP code. Implement auditable correction of task status and a usable verification view. Agree on the Phase 4 selector input/output fields with Developer 1, then load factual event/task inputs and wire Developer 1's selector into a compact handoff through service and MCP. Preserve evidence rules and existing MCP behavior; own any SQLite migration. Do not implement separate ranking logic that duplicates Developer 1's module. Add focused service/MCP tests and report exact integration results.
