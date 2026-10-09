# A.R.C. — Verified Development Memory

**Working Product Name:** A.R.C. — Agent Recall & Continuity

**Product Category:** Developer Tools / Local AI / AI Agent Infrastructure

**Target Platform:** macOS desktop, initially integrated with VS Code and Codex CLI

**Core Technology:** Local AI embeddings, persistent memory, Git and test evidence, and MCP integration

**Development Team:** 1 implementation developer and 1 documentation/video lead

**Primary Target Users:** Developers using AI coding assistants such as Codex, Claude Code, and Cursor

**Project Status:** Phases 0–5 CLI/MCP prototype working; the Phase 5 incident-retrieval gate passed in controlled local-model tests; broader real-project validation remains in progress

**Progress updated:** 2026-10-10. In Part 7, `[x]` means implemented and checked in code, an automated test, a local smoke test, or a clearly labelled user-reported trial. `[ ]` means still open; notes identify work that is only partly implemented. A phase is complete only when its completion gate passes.

---

# PART 1 — PRODUCT DESCRIPTION

## 1.1 What is A.R.C.?

A.R.C. is a local-first development memory and continuity system that preserves project context across AI coding sessions.

It records selected development activities, decisions, code changes, errors, tests, and unresolved tasks. It then uses local AI to organize and retrieve relevant information whenever a developer begins a new session or switches coding assistants.

Unlike a conventional chatbot memory system, A.R.C. is designed to distinguish between what an AI assistant claims to have accomplished and what can actually be confirmed through project evidence.

For example, if Codex says it has implemented an authentication system, A.R.C. can check whether relevant files changed and whether the recorded authentication tests passed.

If the tests were never run, A.R.C. must not label the feature as verified.

When the developer starts a new coding session, A.R.C. provides a compact, evidence-backed handoff describing the current project state.

## 1.2 The Problem

AI coding assistants are increasingly capable of generating, editing, debugging, and testing software.

However, the developer's working context is often fragmented across conversations, tools, projects, and sessions.

A developer might spend several hours working with Codex, implementing features, investigating errors, and making decisions.

After ending the session, they may start a new conversation, switch to Claude Code, or return to the project days later.

Although individual coding tools offer session recovery and persistent context features, the developer may still need to reconstruct information scattered across previous sessions.

Common difficulties include:

- Re-explaining project requirements to a new agent.
- Forgetting why a particular implementation was chosen.
- Repeating approaches that already failed.
- Losing track of unfinished tasks.
- Confusing implemented features with verified features.
- Having different coding agents operate with inconsistent assumptions.
- Spending time searching previous conversations, commits, or terminal logs.

The central problem is not simply forgotten chat messages.

**The problem is the absence of a consistent, evidence-backed view of project progress that can be reused across coding agents.**

## 1.3 Our Solution

A.R.C. acts as an independent memory layer between the developer's project and their coding assistants.

It maintains a local project history, identifies relevant information using on-device AI, and makes that information available to new sessions.

Its core capabilities are:

1. **Project Memory:** Preserve important development events and decisions.
2. **Verified Progress:** Distinguish planned, implemented, tested, and confirmed work.
3. **Smart Continuity:** Generate a relevant handoff for a new coding session.
4. **Experience Memory:** Retrieve previously solved problems and unsuccessful attempts.
5. **Cross-Agent Integration:** Allow compatible coding agents to access the same project memory through MCP.

### Product Vision

Give every software project a persistent, trustworthy memory that survives individual AI coding conversations.

### Value Proposition

**Your coding agent can change. Your project context remains available.**

### What A.R.C. is NOT

A.R.C. is not:

- A replacement for Claude Code or Codex.
- A general-purpose code-generation LLM.
- A tool that automatically fixes every error.
- A full computer surveillance system.
- A simple conversation summarizer.
- A service that claims to know everything an agent did without recording evidence.

---

# PART 2 — HOW A.R.C. ACTUALLY WORKS

## 2.1 Complete User Scenario

Consider a developer building a task-management application.

### Stage A — Start a project

The developer opens A.R.C. and selects their local project folder.

For example:

`/Users/developer/Projects/task-manager`

A.R.C. creates a local project record.

It stores basic information such as:

- Project name
- Project folder
- Git repository identifier, if available
- Current branch and commit
- Selected development environment
- Memory and recording preferences
- Configured test commands

The user can choose which project information A.R.C. is allowed to record.

A.R.C. does not need to capture the entire computer.

### Stage B — Start coding using Codex

The developer opens Codex and asks:

"Build the login screen and connect it to the authentication service."

Codex modifies source files and may run commands or tests.

A.R.C. observes supported project events through local integrations.

Examples include:

- Relevant source files changed.
- New files created.
- Test commands executed through the configured recorder.
- Test results returned.
- A user or agent submitted a development checkpoint.
- An error was encountered.

For the MVP, collection should use Git evidence, a project file watcher, configured test execution, and explicit agent checkpoint tools.

Deeper agent-event integrations can be added later.

### Stage C — Build a development record

Suppose the project produces these events:

| Event | Recorded evidence |
|---|---|
| Login interface created | Source-file changes |
| Authentication code modified | Git diff |
| Authentication test executed | Recorded command and output |
| Authentication test passed | Exit status and test result |
| Logout feature discussed | Task or agent checkpoint |
| Logout feature not implemented | No matching implementation evidence found |

A.R.C. stores these events locally with timestamps and source references.

It does not automatically treat every agent statement as true.

### Stage D — Build a verified project checkpoint

A.R.C. converts the recorded activity into an organized project state.

For example:

**Project:** Task Manager

**Current objective:** Implement user authentication.

**Recorded work:**
- Login UI modified.
- Authentication service updated.
- Authentication tests executed successfully.
- Logout feature remains planned.

**Important decision:**
- Continue using the selected authentication architecture.

**Unresolved issue:**
- Logout functionality still needs implementation and testing.

**Recommended continuation:**
- Inspect the authentication service and complete the logout workflow.

Every important status must refer to supporting evidence.

### Stage E — The developer ends the session

The developer closes Codex.

A.R.C.'s stored information remains in its local database.

Closing a conversation should not remove the saved project checkpoint.

A.R.C. does not need the original agent session to remain active.

### Stage F — Start a new coding session

The next day, the developer opens a new Codex session.

Instead of explaining everything manually, the developer asks:

"Use A.R.C. to check the project state and continue the unfinished authentication work."

Codex calls A.R.C.'s local MCP server.

A.R.C. retrieves the relevant checkpoint and supporting evidence.

The new agent receives a concise handoff describing:

- Current task
- Relevant files
- Completed and unresolved work
- Previous technical decisions
- Recorded test results
- Known failed approaches
- Suggested next investigation

The handoff can be significantly smaller than replaying an entire conversation.

### Stage G — Continue development

Codex examines the retrieved context and current project files.

It may choose to inspect the relevant changes before continuing.

Once the developer or agent performs additional work, new project events become part of A.R.C.'s memory.

The cycle repeats.

**Important:** A.R.C. supplies evidence and context. The coding agent remains responsible for its own decisions, and current files must be rechecked before changes are made.

---

# PART 3 — THE FIVE MAIN FEATURES

## Feature 1 — Verified Project Continuity

**Priority: P0 — Essential**

### Problem solved

A new coding session may not know which work is complete, unfinished, or unverified.

### How it works

A.R.C. maintains structured task records linked to observed evidence.

Each task has an explicit state.

| State | Meaning |
|---|---|
| Planned | The task has been proposed or recorded |
| In progress | Work is actively being tracked |
| Implementation observed | Relevant changes were recorded |
| Tests passed | Named checks passed against a recorded project state |
| Completed / confirmed | The user or an authorized workflow confirmed completion |
| Blocked | An unresolved failure prevents progress |
| Unknown | Evidence is insufficient to determine status |

A.R.C. must distinguish test success from overall feature completion.

For example, a passing unit test does not necessarily prove that the entire login system works correctly.

### Output

A compact project checkpoint with verified facts, unverified claims, important decisions, and outstanding tasks.

### User benefit

A developer can resume work without reconstructing the entire previous conversation.

---

## Feature 2 — Semantic Development Memory

**Priority: P0 — Essential**

### Problem solved

Developers may remember the meaning of an earlier decision or error but not the exact wording.

Traditional keyword search can miss related information.

### How it works

A.R.C. generates vector embeddings from approved development records.

Examples include:

- Error descriptions
- Resolution notes
- Design decisions
- Task descriptions
- Relevant log excerpts
- Previous investigation summaries

A small local embedding model converts these records into numerical vectors.

When a new question arrives, the same local model converts the question into a vector.

A.R.C. compares the question with stored records and retrieves the most relevant results.

### Example

Current question:

"Why did the app crash when I opened the dashboard?"

Previous record:

"Null reference exception during dashboard initialization after session restoration."

Even without identical wording, semantic retrieval may identify the previous event as relevant.

### Output

A ranked set of relevant historical records, each linked to its source.

### User benefit

Find previous decisions and problems without remembering the original phrases.

---

## Feature 3 — Experience Memory

**Priority: P1 — Important differentiator**

### Problem solved

Coding assistants may repeat approaches that were unsuccessful in earlier sessions.

### How it works

A.R.C. records investigation attempts and their observed outcomes.

An incident might contain:

**Problem:** Database connection initialization failure.

**Attempt 1:** Change retry configuration.

**Result:** Test still failed.

**Attempt 2:** Correct connection initialization sequence.

**Result:** Relevant test passed.

**Resolution status:** Confirmed for the recorded project state.

A future error triggers local semantic retrieval.

If A.R.C. finds a sufficiently relevant previous incident, it displays the attempts and results.

### Important limitation

A previously successful approach is not necessarily correct for a new problem.

A.R.C. should present past experience as evidence worth considering, never as a guaranteed solution.

### User benefit

Reduce repeated investigation and help coding agents avoid rediscovering unsuccessful approaches.

---

## Feature 4 — Evidence Timeline

**Priority: P1 — Important for usability and judges**

### Problem solved

Developers often know something broke but cannot remember what happened beforehand.

### How it works

A.R.C. groups timestamped project events into a reviewable sequence.

Examples:

- Last recorded successful run
- Source-file modification
- Dependency-file change
- Failed test execution
- Agent checkpoint
- Confirmed resolution

The user can compare two recorded project states.

Exact differences come from Git or saved snapshots.

Local AI can retrieve and prioritize related events, but does not invent changes.

### Output

A visual timeline with clickable evidence.

### User benefit

Understand the history leading up to a problem without searching several tools manually.

---

## Feature 5 — Cross-Agent Handoff

**Priority: P0 for one agent; P1 for multiple agents**

### Problem solved

Developers switch between different coding agents, each of which may have different conversation context.

### How it works

A.R.C. exposes the project memory through a local MCP server.

The first supported agent requests a structured handoff.

Later, another supported agent uses the same interface.

The handoff should include:

- Project identity and current state
- Relevant history
- Open tasks
- Supporting evidence
- Known limitations
- Links or paths to source files

### Example

Codex records a failed implementation.

The developer starts Claude Code.

Claude retrieves the previous evidence through A.R.C. and examines the unfinished work.

The developer does not need to manually copy the entire earlier conversation.

### User benefit

Project continuity independent of the particular coding agent.

---

# PART 4 — THE ROLE OF LOCAL AI

This is essential for the hackathon.

A.R.C. must remain meaningfully useful even if the cloud coding agents become unavailable.

## 4.1 The Local AI Engine

The core local model is the lightweight `all-minilm` text embedding model, run through Ollama.

The model turns text into semantic representations that can be searched and compared locally.

It does not need to generate code.

### Local AI responsibilities

**A. Meaning-based retrieval**

Identify relevant development memories even when wording differs.

**B. Incident similarity**

Find earlier failures that may be related to a current issue.

**C. Context selection**

Choose useful project history for the current development request rather than returning an entire archive.

**D. Context ranking**

Prioritize information based on semantic relevance, current project identity, recency, and evidence quality.

**E. Optional local source selection**

The current chat path can use `qwen3:1.7b` to select relevant source IDs from retrieved evidence. It then displays the recorded evidence with references. Free-form generated handoff summaries are not implemented; any future summaries must preserve references and uncertainty.

## 4.2 What should NOT use AI?

Ordinary software should handle:

- Git diffs
- File timestamps and hashes
- Test command execution
- Test exit statuses
- Database operations
- Permission checks
- Source-reference linking
- Deterministic task transitions

These operations do not benefit from probabilistic language-model guesses.

## 4.3 Why Local AI Matters

### Privacy

Project histories can contain proprietary source code, internal file paths, client information, and debugging logs.

Local retrieval means those records do not have to be uploaded to a cloud model for every memory query.

### Offline operation

The user can inspect project history, search related incidents, and prepare a handoff without internet access.

### Independence from one coding agent

The memory engine belongs to the local application rather than a single cloud model's conversation.

### Lightweight operation

Embedding models can be substantially smaller than powerful code-generation LLMs.

### Cost

After the local models have been downloaded, repeated local semantic searches do not require per-query cloud inference charges.

## 4.4 Offline AI Boundary

The A.R.C. collector, search, chat, and VS Code extension use local storage and local Ollama models only. Once dependencies and models are installed, these features must work with networking disabled. A.R.C. does not add a cloud AI endpoint or an external database. A separate coding agent connected through MCP may have its own network behavior; that is outside A.R.C.'s local AI path.

Chat uses `all-minilm` for semantic retrieval and optionally uses `qwen3:1.7b` to select evidence. It is not an authority that can mark a task complete or execute a fix.

## 4.5 Local AI Requirements

These are the requirements for the current macOS prototype. The setup commands and a first search are in [README.md](../README.md#set-up-on-macos).

| Requirement | Needed for | Current choice and check |
|---|---|---|
| macOS 14 or newer | Supported macOS setup for Ollama | Apple Silicon supports CPU/GPU inference; Intel Macs run Ollama on CPU. A.R.C.'s validation target is an M1 Mac with 8 GB unified memory, not a proven minimum for every machine. |
| Python 3.11 or newer, Git, and the Python package | CLI, local SQLite store, Git evidence, and MCP | Install `arc-memory` from this repository in a virtual environment. Python's SQLite build must support FTS5. |
| Running local Ollama server | Semantic search and model-assisted chat | The default embedding and fixed chat endpoints use `http://127.0.0.1:11434`; the server must be reachable there. The embedding adapter accepts loopback addresses only. Run with `OLLAMA_NO_CLOUD=1` for Ollama local-only mode. |
| `all-minilm` downloaded in Ollama | Embedding, automatic indexing, and semantic search | Required local model; approximately 46 MB to download. Pull it before going offline. |
| `qwen3:1.7b` downloaded in Ollama | Model-assisted evidence selection in `arc chat` and the extension Chat view | Optional for keyword-only chat; approximately 1.4 GB to download. It is loaded on demand and released after a request. |
| Local disk space | Models, Python environment, and project history | Allow more than the models' approximately 1.5 GB combined download size; SQLite history and install files grow with use. The final free-space and runtime-memory budgets remain to be measured on the target machine. |
| VS Code 1.90 or newer | Editor integration only | The CLI, dashboard, and MCP server do not require VS Code. Node.js/npm are needed to build or test the extension from source, not to run the Python CLI. |

The macOS support boundary and cloud setting come from [Ollama's macOS requirements](https://docs.ollama.com/macos) and [FAQ](https://docs.ollama.com/faq). Download sizes come from the [all-minilm](https://ollama.com/library/all-minilm) and [qwen3:1.7b](https://ollama.com/library/qwen3:1.7b) model pages. The 8 GB target is this project's test machine, not an Ollama minimum.

**Readiness checks:** `python --version` reports 3.11+, `git --version` works, `ollama list` includes each model needed for the selected workflow, and `curl -fsS http://127.0.0.1:11434/api/tags` reaches the local server. Confirm that an `all-minilm` `/api/embed` request returns a vector; a model listed by Ollama alone does not prove inference works. After recording and indexing an event, `arc search "<relevant question>" --semantic-only` must report `"mode": "semantic"` with a source-linked hit. A physical Wi-Fi-off search, cited chat, and fresh MCP trial passed on 2026-10-10; the [Phase 12 report](phase12-offline-report.json) records its scope and result.

Without Ollama, stored history, handoff, and `--keyword-only` search remain available through SQLite FTS5. Without `qwen3:1.7b`, `arc chat --keyword-only` displays recorded evidence. These fallback paths do not satisfy the semantic-search requirement.

---

# PART 5 — TECHNICAL ARCHITECTURE

## 5.1 Recommended Technology Stack

| System | Technology |
|---|---|
| Operating system | macOS first |
| Main language | Python 3.11 |
| Local database | SQLite |
| Text search | SQLite FTS5 |
| Local embeddings | Ollama with all-minilm |
| Local chat source selection | Ollama with qwen3:1.7b, invoked only for a chat request |
| Vector retrieval | sqlite-vec, or simple in-memory cosine search initially |
| Git integration | Git CLI |
| File monitoring | watchdog |
| MCP integration | Official Python MCP SDK |
| Application interface | Streamlit for MVP; PySide6 later if needed |
| Future editor interface | Lightweight VS Code extension in TypeScript, using the existing Python backend |
| Testing | pytest |
| Future free-form explanation model | Optional small quantized LLM; not implemented |
| External coding-agent integration | Codex and Claude Code through compatible local MCP integrations; A.R.C. itself stays local |

Pin dependency versions once a working environment is confirmed, especially the MCP SDK, which has undergone major version changes.

## 5.2 System Components

### Component A — Project Collector

Monitors the explicitly selected repository.

Records:

- Relevant file modifications
- Git state
- Approved task checkpoints
- Configured test-run results
- Recorded error events

Does not require full screen recording.

### Component B — Evidence Database

Stores the actual source of recorded observations.

Every event should include:

- Unique identifier
- Project identifier
- Timestamp
- Event type
- Evidence reference
- Relevant file or test
- Source of the event
- Associated session

### Component C — Local Memory Engine

Creates embeddings and searches relevant historical records.

It should combine semantic retrieval with ordinary filters such as project identity, event type, and recency.

### Component D — Verification Engine

Matches progress claims with observable evidence.

For example:

"Feature implemented" may be associated with file changes.

"Feature tested" requires recorded test execution.

"Feature verified" requires the relevant check to pass against an identified project state.

A.R.C. must report missing evidence instead of guessing.

### Component E — Checkpoint Generator

Builds a structured handoff using:

- Current project state
- Unfinished tasks
- Verified changes
- Relevant earlier decisions
- Associated evidence
- Known failures

### Component F — MCP Server

Provides project-memory functions to compatible coding agents.

### Component G — Dashboard

Allows developers to inspect, search, correct, and control their stored project memory.

### Future Component H — Automatic Observation Worker

Runs only for a project the user has enabled. It coalesces file changes, checks local Git state and new commits, accepts results from supported test integrations, and writes source-labelled events to the existing SQLite store. A standalone `arc watch` path can observe work outside VS Code while running; a saved Git cursor can recover commits when observation restarts. Pause and disable controls stop collection. An intentional pause must not silently backfill activity from the paused period.

### Component I — Offline Answer Engine

Parses local calendar words and date ranges, then uses project-scoped SQLite filters, FTS5, and `all-minilm` embeddings to retrieve bounded evidence. Local `qwen3:1.7b` selects source IDs for semantic and handoff questions; A.R.C. validates those IDs and builds the answer from recorded facts. It labels claims, historical tests, and reported resolutions accurately. Timeline answers count activity by local day, group repeated Git watcher events for readability, include selected earlier milestones, and provide stable continuation. The model never receives the full archive in one prompt.

### Future Component J — VS Code Bridge

Identifies the active workspace, connects a thin VS Code extension to the Python backend over a local stdio protocol, and exposes **A.R.C. Chat** and **A.R.C. Memory**. It does not duplicate the evidence or verification logic in TypeScript. The existing MCP server remains a separate interface over the same project-scoped SQLite data.

---

## 5.3 Proposed Database Entities

The MVP should have a small, structured database.

| Entity | Important fields |
|---|---|
| Project | ID, name, path, repository identity |
| Session | ID, project ID, agent name, start/end time |
| Event | ID, type, timestamp, source, evidence ID |
| Task | ID, description, status, project ID |
| Attempt | ID, task ID, approach, observed outcome |
| Verification | ID, command, exit code, snapshot ID, result |
| Decision | ID, decision text, rationale, source |
| Checkpoint | ID, project state, created time, evidence references |
| Memory | ID, text, vector reference, related entity IDs |
| Collector cursor (future) | Project ID, observation source, last observed Git commit, pause state |
| Index job (future) | Event ID, embedding model, queued/retry state, completion time |

One session may contain multiple events.

One task may have multiple attempts and verifications.

One checkpoint may reference many tasks and events.

Do not store every full source file inside the semantic vector database. Store structured metadata and selected evidence, with links to the actual source.

Future schema changes must migrate the existing `projects`, `tasks`, `events`, `vectors`, and `checkpoints` tables without losing Phase 0 data. Keep event IDs and `arc:event/<id>` references stable. Store timestamps in UTC, display them in the user's local time zone, and label each record's capture source and evidence level. The collector writes factual observations; the memory and chat layers may interpret them but cannot upgrade a task's verification state.

```text
Approved project → file watcher / Git cursor / supported test source
                 → dedupe and privacy filter → SQLite evidence event
                 → bounded automatic index queue → all-minilm vectors
                 → time + type + FTS5 + semantic retrieval → Memory / MCP
                                                        → qwen3:1.7b → Chat
```

The automatic worker and MCP process may share the database, so add SQLite write-ahead logging, a busy timeout, and a single writer policy before concurrent use. No raw terminal scraping, broad filesystem surveillance, or inferred test pass from a file save should be required.

---

# PART 6 — AGENT INTEGRATION

## 6.1 Recommended First Integration

Start with Codex on the local computer.

The local MCP server will expose project-memory tools.

### Initial MCP Tools

**arc_get_project_state**

Returns a compact overview of the project, active tasks, and verification status.

**arc_search_memory**

Accepts a natural-language query and retrieves relevant local development records.

**arc_get_recent_changes**

Returns supported project changes since a specified checkpoint or timestamp.

**arc_get_task_history**

Returns earlier attempts, decisions, and evidence linked to a task.

**arc_create_checkpoint**

Creates a candidate checkpoint from available evidence, with user review or authorized confirmation as appropriate.

### Example Agent Workflow

The developer says:

"Before you continue, check A.R.C. and tell me what is unfinished."

Codex calls `arc_get_project_state`.

It then calls `arc_search_memory` if additional historical context is needed.

A.R.C. responds with structured evidence.

Codex inspects the relevant files and continues.

A.R.C. should not send unrelated project memories automatically.

## 6.2 Integration Strategy

**MVP:** MCP tools plus explicit checkpoints.

**Later:** Supported lifecycle hooks for capturing agent events automatically.

**Future:** Additional integrations with coding platforms that expose appropriate supported APIs.

The availability and detail of automatically captured events will differ by coding platform.

The application must not assume it can access every private internal message, every hidden model decision, or every remote coding session.

---

# PART 7 — DEVELOPMENT PHASES

The original day numbers below show the intended implementation order, not a revised deadline. One developer now owns implementation, while the teammate owns documentation and video promotion. Re-estimate duration after the current Phase 3 gate; keep the phase acceptance criteria. If the hackathon window is shorter, complete the MVP gates before optional features.

## Phase 0 — Technical Feasibility and Scope

**Target: Day 1**

### Objective

Prove that the essential technologies run on the available development computer.

### Tasks

Local AI feasibility:
- [x] Set up Python and Ollama.
- [x] Download a local embedding model (`all-minilm`).
- [x] Convert sample development records into embeddings.
- [x] Retrieve a semantically similar record in local model and CLI tests.
- [x] Confirm that retrieval works with all networking disconnected. A physical Wi-Fi-off semantic search returned the expected source at rank 1 on 2026-10-10; see the [saved report](phase12-offline-report.json). An on-camera segment remains to be recorded.

Application and integration feasibility:
- [x] Initialize the application repository and Python package.
- [x] Create a local SQLite database.
- [x] Test Git state and changed-path collection. The prototype records paths and fingerprints, not raw diffs.
- [x] Create a minimal MCP server.
- [x] Confirm Codex can call a local tool in a fresh session. The user confirmed retrieval of the recorded test session through the configured MCP server on 2026-10-09.

### Deliverables

- Working local embedding experiment
- Working SQLite database
- Working Git evidence collector
- Working minimal MCP connection

### Completion Gate

A new coding session can request a stored record from the local MCP server. **Passed: user-confirmed fresh Codex-session retrieval on 2026-10-09.**

An offline semantic search must return relevant results from previously indexed sample incidents. **Passed by user report on 2026-10-09; capture the exact command/output for presentation evidence.**

---

## Phase 1 — Project Observation

**Target: Days 2–3**

### Objective

Build reliable, permissioned project-event recording.

### Tasks

- [x] Select a local project explicitly with `arc init` or `--project`.
- [x] Record project identity and inspect Git state with `arc state` / `arc capture`.
- [x] Capture changed paths and a Git fingerprint with explicit `arc capture`.
- [x] Create explicit, unconfirmed checkpoints.
- [x] Run configured test commands with captured exit codes, output tails, and fingerprints.
- [x] Associate newly recorded events with an explicitly started session ID. Automatic session start/stop remains future work.
- [x] Save resolvable `arc:event/<id>` source references.
- [x] Display a basic recent-event list in `arc state` JSON. A full timeline view remains open.

### Deliverables

- Project registration
- Session tracking
- Git and file-change records
- Test-result recording
- Local event database

### Completion Gate

The application records a meaningful sequence of real project changes and test results without requiring AI-generated descriptions. **Passed for the explicit-recording prototype:** session `0f5c0c8e905a` captured real changed paths and a passing `pytest` run from this repository; the user retrieved that session through MCP. Automatic observation remains future work.

---

## Phase 2 — Local Semantic Memory

**Target: Days 4–5**

### Objective

Make project history searchable by meaning.

### Tasks

- [x] Normalize the searchable copy of event descriptions for indexing while preserving the original evidence text.
- [x] Generate local embeddings through Ollama.
- [x] Index recorded event summaries in SQLite by event ID.
- [x] Build cosine similarity search over indexed events.
- [x] Filter by project and event type in semantic, keyword, and hybrid search.
- [x] Combine FTS5 and semantic results with reciprocal rank fusion when requested; retain the original semantic default and labelled keyword fallback when embeddings are unavailable or absent.
- [x] Link retrieved records to resolvable source evidence.

### Deliverables

- Local embedding pipeline
- Persistent searchable memory
- Natural-language memory search
- Evidence-linked retrieval results

### Completion Gate

Given an unseen paraphrased query, local AI retrieves a relevant event that ordinary exact keyword matching misses. **Passed in a small predefined local-model evaluation:** semantic search ranked 4/5 expected incidents first versus 1/5 for keyword search; one dependency case ranked second. These synthetic results are an initial check, not general accuracy evidence.

Results must remain available offline. **Passed by user report on 2026-10-09; the output has not yet been archived as demo evidence.**

---

## Phase 3 — Verified Task Tracking

**Target: Days 6–7**

### Objective

Separate claimed progress from evidence-backed progress.

### Tasks

- [x] Create task records.
- [x] Track planned, implementation-observed, tests-passed, and confirmed states.
- [x] Associate captured changes with a task when `--task` is supplied.
- [x] Attach actual configured test results to tasks.
- [x] Detect missing or stale verification.
- [x] Keep unsupported claims in an unverified state.
- [x] Allow the developer to confirm or correct task statuses. `arc task correct` records an auditable downward correction; `arc task review` and `arc_get_task_review` show current evidence and missing checks. A correction cannot create passing-test or confirmed status.

### Deliverables

- Task tracking engine
- Evidence-backed task statuses
- Verification viewer
- Unfinished-task identification
- Source-linked project checkpoint

### Completion Gate

When an agent claims a feature is complete but no test evidence exists, A.R.C. does not incorrectly mark it verified. **Passed in service and MCP tests.** The CLI correction/review journey also passed in a temporary real Git repository on 2026-10-09. The Phase 3 CLI/MCP gate is complete; the Phase 6 dashboard now shows the same evidence review in a graphical view.

---

## Phase 4 — Smart Continuity

**Target: Days 8–9**

### Objective

Generate useful handoffs between development sessions.

### Tasks

- [x] Identify tasks that are not currently confirmed in project state.
- [x] Return recent recorded events and task history on request.
- [x] Prioritize recorded design decisions in a source-linked handoff.
- [x] Select recorded errors, failed tests, and past attempts with explicit labels that do not infer resolution.
- [x] Produce a bounded, relevance-ranked handoff with unfinished and confirmed tasks, current evidence references, session context, and a suggested next step. `arc handoff` reads recorded events without requiring an embedding run.
- [x] Expose the handoff and existing project state/history through the MCP server. `arc_get_project_handoff` is read-only.
- [x] Test retrieval from a fresh Codex session. A read-only 2026-10-09 trial called `arc_get_project_handoff` against the real `.arc/arc.sqlite3` database and returned task `ccd44503aac9`, its `tests_passed` state, Git/test references, and recorded decision/failure/attempt references without conversation context.

### Deliverables

- Smart handoff generator
- Project continuity checkpoint
- Working one-agent MCP integration
- Fresh-session recovery demonstration

### Completion Gate

A completely new coding session retrieves the project's current task, verified work, and relevant prior context without manually pasting the previous conversation.

**Passed on 2026-10-09:** The installed CLI and direct stdio MCP tests passed, and a fresh read-only Codex session retrieved the real project's unfinished Phase 4 task, a passing configured test at the then-current Git fingerprint, and source-linked decision/failure/attempt context. The developer later explicitly confirmed task `ccd44503aac9` (event `arc:event/02aae4fdc34044228a35bb460143b998`). Its current-state label may fall back after subsequent Git changes; the confirmation remains in history. The saved Codex MCP entry still points to the trial database; the real-project trial used a per-run database override.

---

## Phase 5 — Experience Memory

**Target: Days 10–11**

### Objective

Make previous debugging experience useful in new incidents.

### Tasks

- [x] Record debugging attempts and their explicit `failed`, `inconclusive`, or `helped` outcomes as a linked incident timeline. Existing attempt notes can also be linked.
- [x] Connect an error note to an explicitly reported resolution and optional passing configured test. A passing test is labelled current or historical by Git fingerprint; it does not prove the specific error is fixed.
- [x] Generate searchable representations of recorded error and attempt notes.
- [x] Retrieve related recorded incidents using local embeddings in a small smoke test.
- [x] Separate semantically similar incidents with explicitly different recorded causes; if the new cause is unknown, return inspect-only candidates.
- [x] Show source references for the error, recorded cause, attempts, resolution, and linked test in incident history and search results.

### Deliverables

- Incident memory database
- Similar-error search
- Attempt and resolution history
- Source-linked past experience recommendations

### Completion Gate

A new error retrieves a meaningful, nonidentical earlier incident while unrelated examples are not incorrectly presented as confirmed matches.

**Passed in a controlled local-model trial on 2026-10-09:** A paraphrase retrieved the earlier missing-table incident, a broader migration query separated a locked-database incident by its different recorded cause, and an unrelated authentication query returned no incident candidates. Results are always labelled candidates, never confirmed matches. The installed CLI and stdio MCP paths also passed. The 0.55 semantic cutoff and strict keyword fallback need wider calibration with real incidents in Phase 7.

---

## Phase 6 — Product Interface and Cross-Agent Integration

**Target: Days 12–13**

### Objective

Make the product useful and easy to understand.

### Tasks

- [x] Build the main local browser dashboard. It uses Python's loopback HTTP server and bundled HTML/CSS/JavaScript, with no extra runtime package or background service.
- [x] Add a memory search view. Results show retrieval mode, source references, and indexing counts.
- [x] Add task and verification views. A task review displays current evidence, missing checks, and an explicit confirmation action only after current tests pass.
- [x] Add a paginated, filterable project timeline with local-time display and event details.
- [x] Add checkpoint review with candidate and stale labels.
- [ ] Connect a second coding agent if the primary integration is stable.
- [x] Display on-demand local Ollama embedding status and pending-index counts.
- [x] Add project-scoped recording pause and confirmed memory deletion controls.

### Deliverables

- Functional dashboard
- Memory search interface
- Project progress viewer
- Agent handoff experience
- Optional second-agent integration

### Completion Gate

An unfamiliar test user can select a project, understand its progress, and retrieve an unfinished task without developer assistance.

**Implementation status (2026-10-09):** The installed `arc dashboard` command serves the Phase 6 interface on `127.0.0.1`; two automated HTTP tests cover project views, evidence, authorization, pause, and scoped deletion. The unfamiliar-user completion gate is still open. The optional second coding agent remains deferred because one developer owns implementation and the teammate handles documentation and video. Automatic file watching, automatic indexing, chat, and the VS Code extension remain in later phases.

---

## Phase 7 — Validation and Hackathon Preparation

**Target: Day 14**

### Objective

Prove the application is useful, reliable, and genuinely local.

### Tasks

- [x] Test with real recorded project activity beyond the small CLI smoke test. The actual A.R.C. repository now has Phase 6–7 task `7c7e92f66806`, a linked decision/Git observation/passing test, indexed memory, and a real semantic query that returned its decision first. Broader unfamiliar-user use remains open.
- [x] Test semantic retrieval with networking disconnected. User-reported pass on 2026-10-09; a repeatable evidence capture remains open.
- [x] Test a new Codex-session handoff for a real recorded task, passing test, and relevant context. Broader unfamiliar-user trials remain open.
- [x] Test an unsupported completion claim in an automated service test. Broader adversarial testing remains open.
- [x] Measure retrieval accuracy and false candidates on a labelled synthetic set. Phase 7 run: intended incident found in 6/10 paraphrases; candidates returned for 4/15 unrelated or different-cause queries. Broader real-incident calibration remains open.
- [x] Compare the real handoff with README and Git on the same five questions. `docs/HANDOFF_COMPARISON.md` records four source-linked continuity answers from A.R.C. and Git's unique code-diff strength. This is a one-project source-coverage comparison; a timed unfamiliar-user trial remains open before claiming a speed or usability improvement.
- [x] Record a backup demonstration. A 62-second silent screen recording of the live local dashboard is saved as `$HOME/Desktop/ARC-backup-demo.mov`; sampled video frames show Overview, Tasks & evidence, decision Timeline, semantic Memory search, and Checkpoints. This does not show a disconnected network or MCP.
- [x] Prepare the presentation. An offline six-slide deck and timed live-demo runbook are in `docs/PITCH_DECK.html` and `docs/PHASE7_DEMO.md`; rehearsal and recorded video remain open.

### Deliverables

- Stable MVP
- Test results
- Offline verification evidence
- Demonstration video
- Pitch presentation
- Technical documentation

### Completion Gate

The main user journey succeeds repeatedly on the demo machine with no cloud dependency for memory retrieval and checkpoint inspection.

**Current Phase 7 status (2026-10-10):** Labelled local-model retrieval and false-candidate results, a real A.R.C. task with linked Git/test/decision evidence, a source-coverage baseline, a six-slide deck, a timed demo runbook, and an inspected dashboard backup video are available. `scripts/verify_phase7_journey.py` passed twice on the real database over loopback, including semantic retrieval and checkpoint inspection. A physical Wi-Fi-off CLI/chat/MCP run also passed and is recorded in [Phase 12 validation](PHASE_12_VALIDATION.md#physical-offline-trial--2026-10-10). The live unfamiliar-user comparison remains open; this gate is not yet closed.

---

## Future expansion after Phase 7

Phases 0–7 remain the original MVP roadmap. The following phases describe the expansion after that roadmap. Phases 8–11 have working implementations; Phase 10's focused offline gate passed on 2026-10-10. Phase 12 integrated, visual, and resource validation remains open. The original estimates assumed parallel coding and are historical rather than current forecasts.

| Order | Phase | Original estimate | Dependency | User-visible milestone |
|---|---|---:|---|---|
| 1 | Phase 8 — Automatic observation | 2–3 days | Phase 1 recording and privacy rules | Meaningful file and Git activity appears without `arc capture` |
| 2 | Phase 9 — Evidence and indexing | 2–3 days | Phase 8 event stream; Phase 2 embeddings | Supported test results and new memories are indexed without `arc index` |
| 3 | Phase 10 — Offline AI chat | 3–4 days | Phase 9 evidence and search | Grounded answers to project-history questions |
| 4 | Phase 11 — VS Code extension | 3–4 days | Stable Python query and control contract | Chat and Memory views for the selected workspace |
| 5 | Phase 12 — Validation and tuning | 2–3 days | Integrated phases 8–11 | Repeatable offline workflow within the demo machine's resource budget |

### Shared contract before Phase 8

- Preserve the Phase 0 CLI, MCP tool names, evidence states, and `arc:event/<id>` references. Add a database migration and versioned API fields instead of changing their meaning.
- Use one project-scoped service contract for CLI, MCP, the observation worker, and the extension. New operations should cover `observe.start/stop/status`, `activity.list`, `memory.search`, `chat.ask`, `checkpoint.get`, and `privacy.pause/resume` through local adapters. The exact transport can be finalized in Phase 8; the extension should use stdio to avoid a network service.
- Give every automatic event a UTC timestamp, project ID, source type, stable deduplication key, optional session ID, Git fingerprint or commit when available, and resolvable evidence reference. Tag inferred summaries as interpretations, not observations.
- The implementation developer owns indexing, retrieval, answer grounding, model evaluation, collection, storage migration, controls, extension, and MCP compatibility. Keep contract and schema changes small, migrated, and tested. The documentation/video lead records actual setup, validation, and demo results.

## Phase 8 — Automatic Project Observation

**Target: 2–3 working days after Phase 7**

**Implementation status (2026-10-10):** Implemented in `arc/observer.py` (consolidated from two parallel Phase 8 prototypes during the Phase 11 merge). Controls are `arc observer status|enable|pause|resume|disable|start|stop`; `arc watch` runs the worker in the foreground (the Phase 11 VS Code extension supervises it), `arc observer start` runs it detached with its pid in `observer_state.worker_pid`, and `arc observer stop` disables and terminates it. The read-only MCP tool `arc_get_observation_status` reports state. The worker polls Git state at a low interval, records one `git` event per fingerprint change plus an `observer_commit` event per recovered commit, and skips generated directories and the sensitive-path list before hashing — file contents are never stored. A persisted `observer_state` commit cursor recovers commits made while no worker ran; a non-fast-forward HEAD move is treated as a baseline change, not fake commits. Pause suspends collection; resume or disable re-establishes the baseline so deliberately unrecorded activity is not imported. Observation events carry `task_id NULL` and can never confirm a task. Remaining: the Phase 12 validation gates in PHASE_12_VALIDATION.md.

### Objective

Collect useful local development activity without requiring a note or capture command for each change.

### Implementation order

1. Add an opt-in `arc watch` worker for explicitly selected local Git repositories. Watch relevant file create/change/delete events and read Git HEAD/branch at startup, on changes, and at a low-frequency interval. The VS Code extension can later supervise the same worker while the workspace is active.
2. Add a persisted Git commit cursor so a restart can record commits made while the worker was not running. Consider an optional, non-destructive Git hook for faster commit notification, but do not rely on a hook as the only source. Edits outside VS Code are observable while the worker runs; commits are recoverable on restart.
3. Coalesce save bursts, compare a safe path plus file metadata/content hash or Git state, and avoid duplicate observations from watcher and Git signals. Ignore generated directories and sensitive paths before an event or embedding is written. Store changed paths and evidence references, not complete source files.
4. Record observation sessions and add pause, resume, and disable controls. Pausing establishes a new baseline when resumed so deliberately unrecorded activity is not silently imported. Keep the worker idle when no approved workspace is active.

### Milestone and acceptance

- Ten repeated saves with unchanged content do not create ten records; a genuine stable change appears once with a timestamp and source.
- A local commit made outside VS Code appears once, either while the worker runs or through the Git cursor when it restarts. No GitHub remote or push is required.
- A synthetic `.env` change produces no stored event text or embedding. Pause stops new collection; resume and disable behave as labelled.
- No file event alone changes a task to **tests passed** or **completed/confirmed**.

## Phase 9 — Automatic Evidence Enrichment and Indexing (Future)

**Target: 2–3 working days after Phase 8**

### Objective

Keep searchable memory current and attach trustworthy test and error evidence when it is available through supported sources.

### Implementation order

1. Extend the configured test runner and add adapters for VS Code task process results or structured test reports where their command, exit status, and project snapshot can be identified. Supported editor diagnostics may be recorded as error observations, but their disappearance is not proof of a fix. Do not infer a test pass from terminal text, a file save, or a commit. If an external test is not observable through a supported adapter, report its status as unknown.
2. Record failed test events and later passing results as separate facts. Link a proposed fix only when the change and relevant check can be associated; otherwise present a possible relationship that needs review. Keep an agent's progress statement separate from observed evidence.
3. Add a bounded queue that embeds eligible new event summaries automatically with `all-minilm`, batches bursts, retries when Ollama is unavailable, and persists pending work across restarts. Keep FTS5 available if embeddings are delayed; show index freshness in status.
4. Add project, event-type, and time filters to retrieval. Combine keyword and semantic candidates with an explicit ranking policy and deduplicate their source references. Migrate old Phase 0 events without losing them.

### Milestone and acceptance

- A supported test run appears with command, exit code, output reference, and fingerprint; an unrelated terminal command does not become a verified test.
- New eligible events become semantically searchable without `arc index`; after Ollama is stopped and restarted, queued events are indexed once.
- Replaying watcher and test notifications does not create duplicate evidence. Existing CLI and MCP tests still pass after the schema migration.
- A failed check followed by a passing check is reported with both timestamps; task completion still requires the original verification rules and confirmation.

## Phase 10 — Offline Evidence-Backed Chat (Implemented)

**Target: 3–4 working days after Phase 9**

**Implementation and focused acceptance (2026-10-10):** `arc/chat.py` now routes local-day and explicit-date questions, task histories, error/resolution histories, rationale, handoff, and long timelines to bounded project-scoped evidence. It groups repeated observer Git events by local day for chat summaries while leaving the raw timeline intact, adds local-day counts and earlier source-linked milestones, and uses snapshot-stable continuation. `qwen3:1.7b` selects source IDs only; deterministic rendering preserves verification labels and handles missing rationale without inventing an explanation. [The recorded M1 8 GB Wi-Fi-off run](phase10-offline-report.json) passed the six questions below plus a named dashboard-rationale question; outbound TCP was unreachable and all returned citation IDs resolved. Python tests passed 48/48 and extension tests passed 12/12. This focused gate does not close the Phase 12 VS Code visual, full workflow, resource, or broader accuracy checks.

### Objective

Answer questions about the project's history through local retrieval and `qwen3:1.7b`, with references that can be inspected.

### Implementation order

1. Validate `qwen3:1.7b` on the actual M1 8GB machine and add a local-only Ollama chat adapter. Pull the model during setup, use it only for chat requests, limit simultaneous generation to one request, and unload it after each request. Keep `all-minilm` as the retrieval model.
2. Add deterministic SQLite queries for **today**, **yesterday**, a date range, task, error, fix, and chronological timeline. Store UTC timestamps and apply the selected local time zone when interpreting calendar words. A “why” answer needs a recorded rationale such as a decision, task note, or commit message; a diff alone cannot establish intent.
3. Retrieve a bounded set of source-linked events using filters, FTS5, and embeddings. For a long project timeline, walk time windows or milestones and summarize each with its references; support continuation or pagination if the whole period cannot be represented faithfully in one answer.
4. Let the local model select only from retrieved source IDs, validate its selection, and render the answer from recorded evidence. Distinguish observed facts from proposed reasons or fixes, and say when no recorded evidence supports an answer. Chat text cannot alter task verification status or run commands.

### Milestone and acceptance

- With networking disabled, ask: “What happened today?”, “What changed yesterday?”, “What errors did we fix?”, “Why did we implement this feature?”, “Where did we leave off?”, and “Summarize our development timeline.” Answers use the correct local dates and clickable or resolvable event references.
- An answer about a missing rationale says it was not recorded. A claimed fix with no passing check is not presented as verified.
- A fixture history larger than one model context window is covered by bounded retrieval and time-window summaries or clearly marked continuation; the process never sends the entire archive to the model.

## Phase 11 — VS Code Chat and Memory Extension (Future)

**Target: 3–4 working days after Phase 10**

### Objective

Give developers a clean, lightweight editor interface while keeping Python and SQLite as the source of truth.

### Implementation order

1. Create a TypeScript extension with one A.R.C. view container and two sections: **A.R.C. Chat** for questions and cited answers, and **A.R.C. Memory** for captured activity, Git changes, tasks, verification, checkpoints, and timeline filters. Use native VS Code views where practical and a small webview only for the chat interaction.
2. Detect the active local workspace and handle no-workspace and multi-root cases explicitly. Ask for approval before first observation of each project; start or connect to the project-scoped Python worker over stdio, then stop it when the workspace closes. Show collector, index, Ollama, and pause states.
3. Expose pause, resume, disable, search, checkpoint inspection, and evidence navigation. Use VS Code theme tokens, keyboard navigation, and clear timestamp and verification labels. Keep scripts and content local; escape recorded text before rendering it.
4. Stabilize the query and chat response contract and measure cold-start and active memory use. Preserve the existing MCP server so coding agents can still request the same project evidence independently of the extension.

### Milestone and acceptance

- Opening a registered workspace shows its current project without manual path entry; a multi-root workspace selects the intended repository without mixing records.
- A.R.C. Chat answers from local evidence, and A.R.C. Memory shows a new captured event and its source. Pause from the extension stops collection.
- Closing and reopening VS Code restores the project view from SQLite; MCP and CLI still retrieve the same event IDs. No cloud AI or external database is required.

## Phase 12 — Offline, Reliability, and Resource Validation (Future)

**Target: 2–3 working days after Phase 11**

### Objective

Make automatic tracking, long-term chat, and the extension dependable on the actual Mac M1 with 8GB unified memory.

### Implementation order

1. Run a full project session with saves, an outside-editor commit, a failing test, a fix, a passing test, restart, fresh MCP query, and chatbot questions. Repeat with networking disabled after dependencies and models are installed. The documentation/video lead records the observed steps and results.
2. Measure observer idle CPU/RAM, event and index queue growth, model load and chat memory, answer latency, missed/duplicate events, and SQLite size on the demo machine. Set final budgets from these measurements; keep the collector idle when inactive, batch embeddings, and unload chat after idle time. Avoid simultaneous large model work if it causes swapping.
3. Evaluate a labelled history with correct and misleading questions. Count citation validity, date correctness, missing-evidence responses, retrieval quality, false completion claims, and privacy leaks. Fix the failures that threaten the main user journey.
4. Document actual measurements and limits, including activities that cannot be observed outside an active worker or supported Git/test sources. Record a backup demo of the offline workflow.

### Completion gate

On the Mac M1 8GB machine, a new developer can open a project in VS Code, have selected activity recorded automatically, ask local chat what happened, inspect supporting evidence, and retrieve the same state through MCP while disconnected. The observer remains usable during normal editing, the machine avoids sustained swap pressure during chat, excluded files stay out of memory, and unsupported completion claims remain unverified. Report observed resource and accuracy numbers rather than assumed targets.

### References for this future design

- [Ollama `qwen3:1.7b` model](https://ollama.com/library/qwen3:1.7b) for the proposed local conversation model.
- [VS Code view containers and Tree View API](https://code.visualstudio.com/api/extension-guides/tree-view), [webview guidance](https://code.visualstudio.com/api/ux-guidelines/webviews), and [workspace/file-watcher/task APIs](https://code.visualstudio.com/api/references/vscode-api) for the extension plan.

---

# PART 8 — TEAM RESPONSIBILITIES

The team has one implementation developer and one documentation/video lead. See [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md) for the current commands and implementation order, [DOCUMENTATION_AND_VIDEO.md](DOCUMENTATION_AND_VIDEO.md) for the teammate's deliverables, and [TEST_RESULTS.md](TEST_RESULTS.md) for actual results and missing evidence. Phases 8–12 remain future work.

## Implementation developer

Own the application end to end: local embeddings and retrieval, Git/test evidence, SQLite and migrations, task verification, CLI, MCP, and the product interface. The Phase 3 correction/review, Phase 4 handoff, and controlled Phase 5 incident gates passed. The Phase 6 dashboard is implemented; its unfamiliar-user gate and broader Phase 7 retrieval calibration remain. Run technical tests and provide the exact observed results to the documentation/video lead. Preserve source IDs and the distinction between claims and verified evidence.

## Documentation and video lead

Own the README walkthrough, architecture explanation, setup and MCP instructions, test evidence log, known-limitations page, presentation slides, short promotion clip, and backup demonstration video. Reproduce the current user journey, record where instructions fail, and keep claims in screenshots and narration aligned with implemented features. The 2026-10-10 physical offline CLI/chat/MCP result can be used as test evidence; the on-camera offline segment and remaining integrated validation still need to be recorded.

## Shared demo checkpoint

Together, verify a real project session with changes, a configured test, local indexing and search, an evidence-linked checkpoint, and retrieval from a fresh agent session. Record actual command output and network conditions. The implementation developer fixes product failures; the documentation/video lead updates the explanation and video after the behavior is verified.

---

# PART 9 — REQUIRED DELIVERABLES

## Deliverable 1 — Working Local AI Engine

Must support:

- Offline embedding generation
- Semantic memory search
- Ranked retrieval
- Relevant source references
- Persistent indexed memories

## Deliverable 2 — Project Recorder

Must support:

- Project selection
- Relevant change recording
- Test-result collection
- Session tracking
- Persistent storage

## Deliverable 3 — Verified Checkpoint System

Must support:

- Task status tracking
- Evidence association
- Explicit test verification
- Unverified status handling
- Compact project handoffs

## Deliverable 4 — Agent MCP Integration

Must allow a compatible coding agent to:

- Retrieve project state
- Search development history
- Inspect previous attempts
- Access current unresolved tasks
- Request a checkpoint

## Deliverable 5 — Usable Interface

Minimum screens:

- Project dashboard
- Activity timeline
- Memory search
- Task and verification details
- Agent handoff view

## Deliverable 6 — Technical Documentation

Include:

- System architecture
- Local AI model details
- Installation instructions
- MCP setup
- Data schema
- Offline verification method
- Security controls
- Known limitations

## Deliverable 7 — Source Repository

Include:

- Application source code
- Dependency configuration
- Reproducible setup
- Tests
- Example project and synthetic incident fixtures
- Legal model download instructions
- README

## Deliverable 8 — Demo and Evaluation

Include:

- Live coding-session handoff
- Offline memory search
- Verified versus unverified work example
- Retrieval evaluation
- Recorded demonstration backup

---

# PART 10 — TESTING AND EVALUATION

## Test A — Offline Local AI

Disable all internet connectivity.

Ask A.R.C. to search for a prior error using different wording.

**Expected:** The local embedding model retrieves the relevant incident without requesting cloud inference.

## Test B — Session Continuity

Record a project session with completed and unfinished work.

Start a new agent session.

**Expected:** A.R.C. retrieves the current project state and relevant evidence.

## Test C — False Completion Claim

Submit a checkpoint claiming a feature is complete without any recorded tests.

**Expected:** A.R.C. clearly distinguishes the claim from verified execution.

## Test D — Similar Incident Retrieval

Create a dataset of related and unrelated development incidents.

**Expected:** Semantic retrieval performs better than the chosen exact-keyword baseline on a predefined test set.

## Test E — Outdated Context

After generating a checkpoint, modify the project again.

**Expected:** A.R.C. detects that the working tree differs from the checkpoint and does not present stale test evidence as proof of the current state.

## Test F — Cross-Agent Continuity

Record useful context through one supported agent and retrieve it through another.

**Expected:** The new agent accesses the shared local memory through MCP.

## Test G — Privacy

Store test data containing synthetic credentials, API tokens, and sensitive paths.

**Expected:** The system follows configured collection exclusions, applies appropriate redaction, and never sends evidence to a cloud service.

### Initial Evaluation Targets

- All essential memory functions work offline.
- All claimed test-verification results link to recorded test output.
- No unsupported automatic completion claims.
- Strong retrieval quality against a keyword-search baseline.
- New-session handoff identifies the correct unfinished task.
- No unintended cloud transmission of private project data.
- Stable performance on the actual demo hardware.

Measured results must be reported honestly rather than substituted with aspirational numbers.

---

# PART 11 — PRIVACY AND SAFETY

Because A.R.C. stores potentially sensitive development history, privacy should be part of the product architecture.

### Required Controls

1. Explicit project selection and recording consent.
2. Ability to pause project observation.
3. Ignore rules for sensitive paths and files.
4. Redaction of known secret patterns where practical.
5. Local storage with appropriate access permissions.
6. Encryption for sensitive persistent records where supported.
7. User access to view, edit, and delete stored memory.
8. Local-only inference endpoints and no A.R.C. cloud AI or external database connection.
9. Preview of the project evidence exposed through MCP or the local chatbot.
10. No autonomous destructive modification or rollback of source files.

### Trust Boundaries

Agent statements are untrusted claims until supported by evidence.

Captured logs and files are data, not executable instructions for the memory engine.

Test results apply only to the recorded project snapshot and tested scope.

A.R.C. should never silently execute commands found inside retrieved messages or logs.

---

# PART 12 — HACKATHON DEMONSTRATION

## Demonstration Title

**"The Conversation Ended. The Project Didn't."**

### Scene 1 — Begin Development

Open a small application in VS Code.

Use Codex to implement a feature.

Show that A.R.C. is recording selected project events.

### Scene 2 — Establish Actual Progress

Codex modifies files and executes a test.

Some work is completed, but one task remains unfinished.

A.R.C. records the observed changes and verification evidence.

### Scene 3 — End the Session

Close the coding session.

Open a new session with no manually copied conversation history.

### Scene 4 — Retrieve Context

Ask the new agent:

"What did the previous agent finish, and what should I work on next?"

The new agent requests A.R.C. project context through MCP.

A.R.C. returns a compact checkpoint with evidence.

### Scene 5 — Prove Verification

Show that one feature has passing test evidence.

Show another feature that was discussed or implemented but never successfully verified.

A.R.C. must distinguish those statuses.

### Scene 6 — Demonstrate Local AI

Disable internet connectivity.

Ask A.R.C. to retrieve a related previous error with different wording.

Show the local embedding model finding relevant history without cloud inference.

### Scene 7 — Close

Explain:

"We don't need to build another AI that writes code. We need an independent memory that helps the AI tools we already use remember what actually happened.

A.R.C. keeps verified development experience available across coding sessions, while the intelligence that searches and organizes that history runs locally."

---

# PART 13 — FUTURE DEVELOPMENT

## Version 1 — Hackathon MVP

Verified development checkpoints, semantic memory, and one agent integration.

## Version 2 — Cross-Agent Continuity

Improve integrations with Codex, Claude Code, and other compatible agents.

Add richer evidence capture through their documented lifecycle interfaces.

## Version 3 — Regression Guardian

Recognize when a proposed approach resembles a previously unsuccessful one.

Present past evidence and recommend verification before repeating the change.

## Version 4 — Team Memory

Allow teams to share selected, approved project memories and verification records while maintaining clear access controls.

## Version 5 — Verified Development Intelligence

Expand toward safely evaluating historical solutions, suggesting relevant regression tests, and identifying repeated process failures.

Any automatic code-changing or recovery capability should require separate permission and isolated execution.

The planned local-first expansion in **Phases 8–12** adds automatic observation, automatic indexing, an offline chatbot, and a VS Code extension. Those phases extend this roadmap after the MVP; they do not change the Phase 0–7 completion gates or the evidence rules.

---

# PART 14 — DEFINITION OF SUCCESS

The MVP succeeds when:

**A developer can complete part of a task with one AI coding session, end that conversation, start a fresh session, and retrieve an accurate, evidence-backed summary of what was completed, what remains unfinished, and what was actually tested.**

The project must also demonstrate that meaningful semantic memory retrieval operates locally and offline.

Its long-term value will depend on whether this improves developer productivity compared with built-in agent memory, Git history, and ordinary session resumption.

## Final Product Statement

**A.R.C. — Agent Recall & Continuity**

*A local-first memory and verification system that preserves development progress across AI coding agents.*

**The conversation may end. The project memory continues.**
