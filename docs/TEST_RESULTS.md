# A.R.C. test evidence log

This log separates observed results from missing evidence. The documentation/video lead maintains it as the team repeats tests and records screenshots or clips. Do not treat a user report as a saved terminal transcript.

| Date | Check and source | Recorded result | Evidence still needed |
|---|---|---|---|
| 2026-10-09 | Offline semantic search, user report | User confirmed networking was off and `--semantic-only` returned `"mode": "semantic"`. | Save the exact command, returned event reference, and terminal output during a repeat trial. |
| 2026-10-09 | `.venv/bin/python -m pytest -q`, local run | 13 tests passed in 4.25 seconds after the documentation update. | Add a screenshot or captured transcript for the demo package if desired. |
| 2026-10-09 | `.venv/bin/python -m scripts.evaluate_retrieval`, local run | Seven synthetic records and five queries: semantic top-1 **4/5**, semantic recall@3 **5/5**, keyword top-1 **1/5**. An unrelated query still returned a low-scoring candidate. | Expand to realistic incidents and record false matches before claiming general retrieval accuracy. |
| 2026-10-09 | Fresh Codex MCP session, user report | The earlier trial session was retrieved through the configured local MCP server. | The separate Phase 4 handoff trial is recorded below; repeat with real verified work. |
| 2026-10-09 | Phase 3 `.venv/bin/python -m pytest -q` and installed `arc` smoke run | 16 tests passed. A temporary Git project completed `init → task add → capture → test → confirm → correct → review`; correction returned `implementation_observed` and review showed its prior test did not count. | Repeat against a real work session when recording the final demo; the temporary project was only a local smoke test. |
| 2026-10-09, 20:18 Manila | Phase 3 manual CLI trial, user-pasted terminal output and local `.arc/first-test.sqlite3` | Task `fbecf869da18` was corrected to `planned`; `arc task review` showed no linked change or passing test and listed both missing checks. Correction event: `arc:event/8e4bbbdb113543e292bff2d2dd7fbddf`. | Capture a screenshot or transcript for the demo package. This trial checks the planned state and review output, not the complete change/test/confirmation journey. |
| 2026-10-09 | Phase 4 `.venv/bin/python -m pytest -q` | 18 tests passed in 8.64 seconds, including handoff selection, stale/corrected evidence rejection, and a real stdio MCP client/server call to `arc_get_project_handoff`. | Test a real development task with current passing test evidence and a fresh Codex session. |
| 2026-10-09 | Installed `arc handoff` CLI smoke test in a temporary Git project and SQLite database | Returned one unfinished `planned` task and selected `decision`, `failure`, and `attempt` events, each with an `arc:event/<id>` reference. | Temporary data proves the command path, not handoff quality for a real work session. |
| 2026-10-09 | Fresh ephemeral read-only Codex session, `arc_get_project_handoff`, configured `.arc/first-test.sqlite3` | Codex called the MCP tool and reported practice task `fbecf869da18` plus references `arc:event/8e4bbbdb113543e292bff2d2dd7fbddf`, `arc:event/b2b46dfd3bb347a5b7cce042232cc071`, and `arc:event/8cdb47b04bf9427796a294a94d81d008`. | This trial alone did not prove the full gate; the real-database trial appears below. |
| 2026-10-09 | Real `.arc/arc.sqlite3` work session, installed CLI | Session `f3b19a48ed58` recorded task `ccd44503aac9`, a design decision, test-collection failure, debugging attempt, Git observation, and a passing configured test. The task became `tests_passed` and was left unconfirmed. | Review the task before explicit developer confirmation. Later Git changes require a new test at the new fingerprint. |
| 2026-10-09 | Fresh ephemeral read-only Codex session, one-run MCP override to real `.arc/arc.sqlite3` | Codex called `arc_get_project_handoff` once and returned task `ccd44503aac9` as `tests_passed`, Git reference `arc:event/be2b6d4436b248aab3d7f848d4dae1a6`, then-current test reference `arc:event/f5dda7936a2a495fbbf22b75422a5a53`, and decision/failure/attempt references. No previous conversation was pasted. | This proves the Phase 4 fresh-session gate for one real task. Repeat with other projects and unfamiliar users in Phase 7. The recorded test must be rerun after later documentation edits change the Git fingerprint. |
| 2026-10-09 | Phase 4 confirmation, user-pasted CLI output | The developer reviewed task `ccd44503aac9` at `tests_passed` and explicitly confirmed it. Confirmation event: `arc:event/02aae4fdc34044228a35bb460143b998`. | Later Phase 5 code changes make the associated Git fingerprint historical; the confirmation event remains in task history. |
| 2026-10-09 | Phase 5 `.venv/bin/python -m pytest -q` | 22 tests passed in 13.87 seconds. The live `all-minilm` incident test retrieved a nonidentical migration error, separated a similar locked-database error by recorded cause, and returned no incident for an unrelated authentication query. Direct stdio MCP calls read and searched incidents. | Calibrate the 0.55 cutoff and false-match rate on a larger labelled set of real incidents. This controlled fixture does not prove general accuracy. |
| 2026-10-09 | Installed Phase 5 CLI smoke test, temporary Git project and database | `incident open → attempt → test → resolve → index → search` worked. The reported resolution linked a current passing test, five events were indexed, and the paraphrase returned one candidate with cosine 0.774. | Repeat with real debugging work and capture the terminal output for the demo. No real project incident was written by this smoke test. |

## Template for the next trial

Copy this block for each repeatable test:

```text
Date/time and time zone:
Machine and OS:
Project and database (omit private paths if publishing):
Network state:
Exact command or agent question:
Expected result:
Actual result and source event ID:
Pass/fail/partial:
Screenshot or video filename:
Limitations or follow-up:
```
