# Documentation and video promotion

The second team member owns the product explanation and evidence package while the implementation developer builds A.R.C. This is a non-coding role. Use the [development plan](DEVELOPMENT_PLAN.md) as the feature checklist and the [project workflow](PROJECT_WORKFLOW.md) for commands that actually run today. Describe implemented behavior separately from planned Phases 8–12.

## Documentation deliverables

| Deliverable | What to include | Acceptance check |
|---|---|---|
| Setup guide | Mac prerequisites, Python environment, Ollama `all-minilm` pull, the real versus trial database, and MCP setup. | A new person follows [README.md](../README.md) without private help and reaches `arc state`. |
| Product walkthrough | The problem, local AI architecture, what SQLite stores, what evidence states mean, and how sessions, linked incidents, search, and MCP work. | A reader can identify what is observed, what is a claim, and where a source event can be inspected. |
| Test evidence log | Date, machine, network state, exact command, expected result, actual result, and a screenshot or short clip for each gate. | Every “passed” label has a reproducible observation; missing tests stay open. |
| Limitations and roadmap | Explain that current recording/indexing are manual and identify Phase 8–12 features as future work. | No screenshot or description implies a watcher, chat UI, or dashboard exists today. |

Maintain the starter [test evidence log](TEST_RESULTS.md) as the team repeats field trials. Do not put credentials, raw private logs, or the `.arc/` database into the repository. Redact project names or paths if needed before publishing screenshots.

## Video deliverables

1. **Short promotion clip, about 30–60 seconds:** show the lost-context problem, one real A.R.C. search result with its source reference, and the promise of local continuity. Label future visuals as concepts.
2. **Backup demo, about 2–3 minutes:** record an actual session with a task, Git capture, configured test, `arc index`, semantic search, `arc handoff`, and a new Codex session calling `arc_get_project_handoff`. If time allows, show one linked incident and explain that a similar error is a candidate, not a confirmed diagnosis. Include the disconnected-network semantic search once its conditions are recorded.
3. **Presentation assets:** title slide, architecture diagram, one verified-versus-unverified example, measured test results, known limits, and the next roadmap milestone.

Capture the terminal commands and returned event IDs, not a scripted animation. Verify the recording is readable at presentation size and plays locally with networking off. Export a common video format and keep a local backup on the demo machine. Do not claim a feature or performance result that the team has not run.

## This week's practical checklist

- Follow the README from a clean terminal and note any confusing or incorrect instruction for the implementation developer to fix.
- Record the user-reported 2026-10-09 offline semantic-search result with its exact command and network state once the terminal output or a repeat capture is available.
- Draft the product walkthrough and a short voiceover using the current CLI/MCP behavior, including linked incident evidence.
- Film the backup demo using the passed Phase 4 real-project handoff: show the task, Git and test references, a decision, a failure, and an attempt. Capture the working local search separately.
- Keep the plan's completed checkboxes aligned with actual test evidence and label demonstrations of future features as concepts.

## Brief to give your Codex session

> I own documentation and video promotion for A.R.C. Read `README.md`, `docs/DEVELOPMENT_PLAN.md`, `docs/PROJECT_WORKFLOW.md`, and `docs/TEST_RESULTS.md`. Verify the setup and commands against the current repository, improve the walkthrough and known limitations, and maintain a dated evidence log. Draft a 30–60 second promotion script and a 2–3 minute backup demo shot list using only implemented behavior. Show source event references, local search, verified versus unverified status, and the current manual capture/indexing steps. Keep Phases 8–12 labelled as future work. Do not change application code or claim an unrun test passed.
