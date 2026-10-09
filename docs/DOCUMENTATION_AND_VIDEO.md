# Documentation and video promotion
Date: 10/10/26
The second team member owns the product explanation and evidence package while the implementation developer builds A.R.C. This is a non-coding role. Use the [development plan](DEVELOPMENT_PLAN.md) as the feature checklist and the [project workflow](PROJECT_WORKFLOW.md) for commands that actually run today. Describe implemented behavior separately from planned Phases 8–12.

## Documentation deliverables

| Deliverable | What to include | Acceptance check |
|---|---|---|
| Setup guide | Mac prerequisites, Python environment, Ollama `all-minilm` pull, the real versus trial database, and MCP setup. | A new person follows [README.md](../README.md) without private help and reaches `arc state`. |
| Product walkthrough | The problem, local AI architecture, what SQLite stores, what evidence states mean, and how sessions, linked incidents, search, and MCP work. | A reader can identify what is observed, what is a claim, and where a source event can be inspected. |
| Test evidence log | Date, machine, network state, exact command, expected result, actual result, and a screenshot or short clip for each gate. | Every “passed” label has a reproducible observation; missing tests stay open. |
| Limitations and roadmap | Explain that current recording/indexing are manual and identify Phase 8–12 features as future work. | Screenshots show the implemented dashboard accurately; no screenshot implies a watcher or chat UI exists today. |

Maintain the starter [test evidence log](TEST_RESULTS.md) as the team repeats field trials. Do not put credentials, raw private logs, or the `.arc/` database into the repository. Redact project names or paths if needed before publishing screenshots.

## Video deliverables

Use the ready-to-read [vlog script](VLOG_SCRIPT.md) for the short promotion clip and the narrated backup demo.

1. **Short promotion clip, about 30–60 seconds:** show the lost-context problem, one real A.R.C. search result with its source reference, and the promise of local continuity. Label future visuals as concepts.
2. **Backup demo, about 2–3 minutes:** follow [the Phase 7 shot list](PHASE7_DEMO.md) with the actual dashboard, task evidence, local semantic search, and source event. If time allows, show MCP handoff and a linked incident as a candidate, not a confirmed diagnosis. Include the disconnected-network semantic search only after its conditions are recorded.
3. **Presentation assets:** the offline [pitch deck](PITCH_DECK.html) contains the problem, architecture, live-demo cues, measured test results, known limits, and next roadmap milestone. Rehearse its claims against [Phase 7 results](PHASE7_VALIDATION.md).

Capture the terminal commands and returned event IDs, not a scripted animation. Verify the recording is readable at presentation size and plays locally with networking off. Export a common video format and keep a local backup on the demo machine. Do not claim a feature or performance result that the team has not run.

## This week's practical checklist

- Follow the README from a clean terminal and note any confusing or incorrect instruction for the implementation developer to fix.
- Record the user-reported 2026-10-09 offline semantic-search result with its exact command and network state once the terminal output or a repeat capture is available.
- Rehearse the deck with the current dashboard, CLI/MCP behavior, and linked incident evidence. Treat the measured 6/10 incident recall and 4/15 false-candidate result as a limitation, not a success claim.
- Review the saved 62-second dashboard backup at `$HOME/Desktop/ARC-backup-demo.mov`. It shows the Phase 6–7 task, current test evidence, a dated decision, semantic search, and checkpoints. The fuller narrated demo should still cover the Phase 4 failure/attempt, MCP, and a separately documented network-off run.
- Keep the plan's completed checkboxes aligned with actual test evidence and label demonstrations of future features as concepts.

## Brief to give your Codex session

> I own documentation and video promotion for A.R.C. Read `README.md`, `docs/DEVELOPMENT_PLAN.md`, `docs/PROJECT_WORKFLOW.md`, and `docs/TEST_RESULTS.md`. Verify the setup and commands against the current repository, improve the walkthrough and known limitations, and maintain a dated evidence log. Draft a 30–60 second promotion script and a 2–3 minute backup demo shot list using only implemented behavior. Show source event references, local search, verified versus unverified status, and the current manual capture/indexing steps. Keep Phases 8–12 labelled as future work. Do not change application code or claim an unrun test passed.
