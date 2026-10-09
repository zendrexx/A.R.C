# A.R.C. — Verified Development Memory

**Working Product Name:** A.R.C. — Agent Recall & Continuity

**Product Category:** Developer Tools / Local AI / AI Agent Infrastructure

**Target Platform:** macOS desktop, initially integrated with VS Code and Codex CLI

**Core Technology:** Local AI embeddings, persistent memory, Git and test evidence, and MCP integration

**Development Team:** 2 developers

**Primary Target Users:** Developers using AI coding assistants such as Codex, Claude Code, and Cursor

**Project Status:** Phase 0 CLI and MCP prototype implemented; end-to-end validation still in progress

**Progress updated:** 2026-10-09. In Part 7, `[x]` means implemented and checked in code, an automated test, or a local smoke test. `[ ]` means still open; notes identify work that is only partly implemented. A phase is complete only when its completion gate passes.

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

The core local model will initially be a lightweight text embedding model.

A candidate is `all-minilm`, run through Ollama.

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

**E. Optional local summarization**

A small local language model may create concise handoff summaries from retrieved evidence.

Summaries must preserve references and uncertainty.

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

## 4.4 Optional Cloud AI

A.R.C. may provide a separate cloud-assisted investigation feature.

The user could select relevant evidence and explicitly send it to a coding model for deeper analysis.

Cloud AI can help with:

- Complex code reasoning
- Generating possible fixes
- Explaining unfamiliar frameworks
- Reviewing proposed changes
- Creating tests

However, all core memory functions must continue to work without it.

**The cloud model is the coding specialist. A.R.C. is the independent local memory and evidence layer.**

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
| Vector retrieval | sqlite-vec, or simple in-memory cosine search initially |
| Git integration | Git CLI |
| File monitoring | watchdog |
| MCP integration | Official Python MCP SDK |
| Application interface | Streamlit for MVP; PySide6 later if needed |
| Testing | pytest |
| Local explanation model | Optional small quantized LLM |
| Cloud coding assistants | Codex and Claude Code through compatible integrations |

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

One session may contain multiple events.

One task may have multiple attempts and verifications.

One checkpoint may reference many tasks and events.

Do not store every full source file inside the semantic vector database. Store structured metadata and selected evidence, with links to the actual source.

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

The recommended schedule is a 14-day implementation plan for two developers.

If the actual hackathon window is shorter, complete the P0 milestones first and cut optional features.

## Phase 0 — Technical Feasibility and Scope

**Target: Day 1**

### Objective

Prove that the essential technologies run on the available development computer.

### Tasks

Developer 1:
- [x] Set up Python and Ollama.
- [x] Download a local embedding model (`all-minilm`).
- [x] Convert sample development records into embeddings.
- [x] Retrieve a semantically similar record in local model and CLI tests.
- [ ] Confirm that retrieval works with all networking disconnected. It passed with Ollama cloud features disabled, but a disconnected-network trial is still needed.

Developer 2:
- [x] Initialize the application repository and Python package.
- [x] Create a local SQLite database.
- [x] Test Git state and changed-path collection. The prototype records paths and fingerprints, not raw diffs.
- [x] Create a minimal MCP server.
- [ ] Confirm Codex can call a local tool in a fresh session. An automated MCP client completed a stdio round trip; Codex itself has not been connected yet.

### Deliverables

- Working local embedding experiment
- Working SQLite database
- Working Git evidence collector
- Working minimal MCP connection

### Completion Gate

A new coding session can request a stored record from the local MCP server. **Open: fresh Codex-session test.**

An offline semantic search must return relevant results from previously indexed sample incidents. **Open: disconnected-network test.**

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
- [ ] Associate events with sessions.
- [x] Save resolvable `arc:event/<id>` source references.
- [x] Display a basic recent-event list in `arc state` JSON. A full timeline view remains open.

### Deliverables

- Project registration
- Session tracking
- Git and file-change records
- Test-result recording
- Local event database

### Completion Gate

The application records a meaningful sequence of real project changes and test results without requiring AI-generated descriptions. **Open: record and review an end-to-end sequence from a real development session.**

---

## Phase 2 — Local Semantic Memory

**Target: Days 4–5**

### Objective

Make project history searchable by meaning.

### Tasks

- [ ] Normalize stored event descriptions consistently. Basic redaction and length limits exist.
- [x] Generate local embeddings through Ollama.
- [x] Index recorded event summaries in SQLite by event ID.
- [x] Build cosine similarity search over indexed events.
- [ ] Filter by project and event type. Project scoping works; event-type filtering remains open.
- [ ] Combine exact search with semantic search. FTS5 currently serves as a labelled fallback when embeddings are unavailable.
- [x] Link retrieved records to resolvable source evidence.

### Deliverables

- Local embedding pipeline
- Persistent searchable memory
- Natural-language memory search
- Evidence-linked retrieval results

### Completion Gate

Given an unseen paraphrased query, local AI retrieves a relevant event that ordinary exact keyword matching misses. **Open: predefined retrieval evaluation against the keyword baseline.**

Results must remain available offline. **Open: disconnected-network trial.**

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
- [ ] Allow the developer to confirm or correct task statuses. Explicit confirmation exists; correction/editing does not.

### Deliverables

- Task tracking engine
- Evidence-backed task statuses
- Verification viewer
- Unfinished-task identification
- Source-linked project checkpoint

### Completion Gate

When an agent claims a feature is complete but no test evidence exists, A.R.C. does not incorrectly mark it verified. **Passed in an automated service test; the full Phase 3 interface is still open.**

---

## Phase 4 — Smart Continuity

**Target: Days 8–9**

### Objective

Generate useful handoffs between development sessions.

### Tasks

- [x] Identify tasks that are not currently confirmed in project state.
- [x] Return recent recorded events and task history on request.
- [ ] Select important design decisions for the handoff. Decision notes can be recorded but are not prioritized yet.
- [ ] Select known failures and past attempts for the handoff. Error and attempt notes can be recorded but are not linked or prioritized yet.
- [ ] Produce a relevance-ranked compact handoff. Current project state is a basic structured summary.
- [x] Expose project state and history through the MCP server.
- [ ] Test retrieval from a fresh Codex session.

### Deliverables

- Smart handoff generator
- Project continuity checkpoint
- Working one-agent MCP integration
- Fresh-session recovery demonstration

### Completion Gate

A completely new coding session retrieves the project's current task, verified work, and relevant prior context without manually pasting the previous conversation.

---

## Phase 5 — Experience Memory

**Target: Days 10–11**

### Objective

Make previous debugging experience useful in new incidents.

### Tasks

- [ ] Record debugging attempts and outcomes as a linked history. Basic `attempt` and `error` notes exist.
- [ ] Connect failures to successful resolutions.
- [x] Generate searchable representations of recorded error and attempt notes.
- [x] Retrieve related recorded incidents using local embeddings in a small smoke test.
- [ ] Distinguish similar errors with different causes.
- [x] Show source references for retrieved records. Incident-specific evidence links remain open.

### Deliverables

- Incident memory database
- Similar-error search
- Attempt and resolution history
- Source-linked past experience recommendations

### Completion Gate

A new error retrieves a meaningful, nonidentical earlier incident while unrelated examples are not incorrectly presented as confirmed matches.

---

## Phase 6 — Product Interface and Cross-Agent Integration

**Target: Days 12–13**

### Objective

Make the product useful and easy to understand.

### Tasks

- [ ] Build the main dashboard.
- [ ] Add a memory search view. CLI and MCP search already work.
- [ ] Add task and verification views. CLI and MCP state already expose this data.
- [ ] Add a project timeline. `arc state` currently lists only recent events in JSON.
- [ ] Add checkpoint review. The CLI can save candidate checkpoints and report staleness.
- [ ] Connect a second coding agent if the primary integration is stable.
- [ ] Display local AI and connection status.
- [ ] Add pause and deletion controls.

### Deliverables

- Functional dashboard
- Memory search interface
- Project progress viewer
- Agent handoff experience
- Optional second-agent integration

### Completion Gate

An unfamiliar test user can select a project, understand its progress, and retrieve an unfinished task without developer assistance.

---

## Phase 7 — Validation and Hackathon Preparation

**Target: Day 14**

### Objective

Prove the application is useful, reliable, and genuinely local.

### Tasks

- [ ] Test with real recorded project activity beyond the small CLI smoke test.
- [ ] Test semantic retrieval with networking disconnected.
- [ ] Test a new Codex-session handoff.
- [x] Test an unsupported completion claim in an automated service test. Broader adversarial testing remains open.
- [ ] Measure retrieval accuracy and false matches on a labelled set.
- [ ] Compare handoff quality against a README or Git-only baseline.
- [ ] Record a backup demonstration.
- [ ] Prepare the presentation. Architecture, setup, and limitations are documented in `docs/IMPLEMENTATION.md` and `README.md`.

### Deliverables

- Stable MVP
- Test results
- Offline verification evidence
- Demonstration video
- Pitch presentation
- Technical documentation

### Completion Gate

The main user journey succeeds repeatedly on the demo machine with no cloud dependency for memory retrieval and checkpoint inspection.

---

# PART 8 — TEAM RESPONSIBILITIES

## Developer 1 — Local AI and Memory Infrastructure

**Primary ownership:**

- Ollama and embedding integration
- Memory indexing
- Semantic retrieval
- Incident similarity
- Retrieval ranking
- Search evaluation
- Evidence-aware context selection
- Optional local summarization
- Offline AI verification

**Primary deliverable:** A reliable local intelligence engine that retrieves relevant project memory from recorded evidence.

## Developer 2 — Agent Integration and Product

**Primary ownership:**

- Project registration
- Git and file-event collection
- Test-run tracking
- SQLite data models and application services
- Task verification
- MCP server
- Dashboard and UX
- Session checkpoint management
- Integration and demonstration

**Primary deliverable:** A usable application that collects trustworthy evidence and makes it available to coding agents.

## Shared Responsibilities

- Finalize interfaces between components.
- Define event and checkpoint schemas.
- Test the full workflow daily.
- Protect sensitive information.
- Conduct developer usability tests.
- Prepare the final hackathon demonstration.

Both developers should agree on shared data structures before working independently.

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

**Expected:** The system follows configured collection exclusions, applies appropriate redaction, and never sends evidence to a cloud service without approval.

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
8. Clear separation between local inference and cloud API functionality.
9. Explicit preview before sending project evidence to cloud AI.
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
